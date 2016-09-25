#!/usr/bin/python

from pyVmomi import vim
from pyVmomi import vmodl
from pyVim.connect import SmartConnect, Disconnect
import atexit
import random
import datetime
import time
import requests
requests.packages.urllib3.disable_warnings()
import ssl

try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context


DOCUMENTATION = '''
---
module: vcenter
short_description: Perform tasks on a vCenter server
description:
     - Perform tasks on a vCenter server. relies on pyvmomi
version_added: "n/a"
options:
  vcenter_hostname:
    description:
     - hostname of the vCenter server
    required: true
    default: null
    aliases: []
  username:
    description:
      - Username to connect to vCenter server as.
    required: true
    default: null
    aliases: []
  password:
    description:
      - Password of the vCenter user
    required: true
    default: null
    aliases: []
  vnics:
    description:
      - key, value pairs of virtual nics. see examples.
    required: false
    default: none
    aliases: []
  action:
    description:
      - vCenter action to take on the VM.
    required: true
    default: null
    aliases: []
    choices: [set_perms, restart, revert_snapshot, snapshot, delete_snapshot,  shutdown, clone, delete, upgrade_tools, reconfigure, gather_facts]
  ss_name:
    description:
      - snapshot name. for use with action: revert_snapshot
    required: false
    default: false
    aliases: []
  dns_list:
    description:
     - list of dns servers to send to the customization spec.
    required: false
    default: null
    aliases: []
  suffix_list:
    description:
      - list of dns suffixes to send to the customization spec.
  full_name:
    description:
      - Full name of user to send to the customization spec.
    required: false
    default: null
    aliases: []
  org_name:
    description:
      - Organization Name to send to the customization spec.
    required: false
    default: null
    aliases: []
  login_password:
    description:
      - Password for the Administrator user to send to the customization spec.
    required: false
    default: null
    aliases: []
  role:
    description:
      - the roleID you wish to grant to the users. for use with action: set_perms
    required: false
    default: null
    aliases: []
  users:
    description:
      - A list of user accounts to grant access to. for use with action: set_perms
    required: false
    default: null
    aliases: []
  vm_name:
    description:
      - VM you wish to take vCenter actions on.
    required: true
    default: null
    aliases: []
  propagate:
    description:
      - Weather or not to propagate roles to child entities. for use with action: set_perms
    required: false
    default: false
    choices: [True, False]
    aliases: []
  group:
    description:
     - Weather or not the users list is a group. for use with action: set_perms
    required: false
    default: false
    aliases: []
  domain:
    description:
      - The domain that the users belong to. for use with action: set_perms
    required: false
    default: null
    aliases: []
  reset:
    description:
      - If True, list that's passed to entity will overwrite entity permissions, if False, list will be appended to entity. for use with action: set_perms
    required: false
    default: false
    choices: [True, False]
    aliases: []
'''

EXAMPLES = '''
# clone a VM from template, with linux guest customizations.
- vcenter:
  vcenter_hostname: vcenter.mydomain.local
  username: administrator@local-domain
  password: secret
  vm_name: newvm001
  template: rhel6_64_template
  vnics:
    nic1:
      vswitch: 'Virtual Machine Network'
      ip: 203.0.113.4
      gateway: 203.0.113.1
      netmask: 255.255.255.0
      network_type: dvs
  dns_list:
    - 8.8.8.8
    - 4.4.4.4
  suffix_list:
    - example.com
    - example.net
  datacenter_name: Datacenter1
  cluster_name: Cluseter1
  vm_disk:
    disk1:
      size_gb: 20
      type: thin
    disk2:
      size_gb: 40
      type: thick
  datastore: STORAGE_1
  domain_name: example.com
  num_cpus: 1
  memory_mb: 2048
  action: clone
  os_family: linux
  vm_folder: 'FolderName'

'''

try:
    import json
except ImportError:
    import simplejson as json


def main():
    """Pulls in params from ansible, sets up connection to vCenter """
    module = AnsibleModule(
        argument_spec=dict(
            vcenter_hostname=dict(required=True, type='str'),
            username=dict(required=True, type='str'),
            password=dict(required=True, type='str'),
            role=dict(required=False, type='int'),
            users=dict(required=False, type='list'),
            vm_name=dict(required=True, type='str'),
            ss_name=dict(required=False, type='str'),
            ss_memory=dict(required=False, default=False, type='bool'),
            action=dict(required=True, type='str',
                        choices=['set_perms', 'restart', 'snapshot',
                                 'revert_snapshot', 'delete_snapshot',
                                 'shutdown', 'clone', 'delete', 'upgrade_tools',
                                 'reconfigure', 'gather_facts',
                                 'change_uuid', 'relocate_vm']),
            template=dict(required=False, default=False, type='str'),
            propagate=dict(
                required=False,
                default=False,
                type='bool'),
            group=dict(required=False, default=False, type='bool'),
            vm_folder=dict(required=False, default=None, type='str'),
            domain=dict(required=False, default=None, type='str'),
            datacenter_name=dict(required=False, default=None, type='str'),
            cluster_name=dict(required=False, default=None, type='str'),
            datastore=dict(required=False, default=None, type='str'),
            domain_name=dict(required=False, default=None, type='str'),
            num_cpus=dict(required=False, default=None, type='str'),
            memory_mb=dict(required=False, default=None, type='str'),
            vm_disk=dict(required=False, default={}, type='dict'),
            reset=dict(required=False, default=None, type='str'),
            vnics=dict(required=False, default={}, type='dict'),
            dns_list=dict(required=False, default=None, type='list'),
            vm_uuid=dict(required=False, default=None, type='str'),
            suffix_list=dict(required=False, default=None, type='list'),
            full_name=dict(required=False, default=None, type='str'),
            org_name=dict(required=False, default=None, type='str'),
            os_family=dict(
                required=False,
                default='linux',
                type='str',
                choices=['linux', 'windows']),
            resource_pool=dict(required=False, default=None, type='str'),
            login_password=dict(required=False, default=None, type='str'),
        ),
        supports_check_mode=False
    )


# set vars from module
    vcenter_hostname = module.params['vcenter_hostname']
    username = module.params['username']
    password = module.params['password']
    action = module.params['action']
    role_id = module.params['role']
    users = module.params['users']
    os_family = module.params['os_family']
    vnics = module.params['vnics']
    resource_pool = module.params['resource_pool']
    template = module.params['template']
    vm_folder = module.params['vm_folder']
    vm_name = module.params['vm_name']
    vm_disk = module.params['vm_disk']
    propagate = module.params['propagate']
    group = module.params['group']
    domain = module.params['domain']
    ss_name = module.params['ss_name']
    ss_memory = module.params['ss_memory']
    reset = module.params['reset']
    dns_list = module.params['dns_list']
    suffix_list = module.params['suffix_list']
    full_name = module.params['full_name']
    org_name = module.params['org_name']
    datacenter_name = module.params['datacenter_name']
    cluster_name = module.params['cluster_name']
    datastore = module.params['datastore']
    domain_name = module.params['domain_name']
    num_cpus = module.params['num_cpus']
    memory_mb = module.params['memory_mb']
    login_password = module.params['login_password']
    vm_uuid = module.params['vm_uuid']

    #context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    #context.verify_mode = ssl.CERT_NONE
    # sslContext=context
    si = SmartConnect(
        host=vcenter_hostname,
        user=username,
        pwd=password,
        port=int(443))

    content = si.RetrieveContent()

    if action == 'set_perms':
        vm = find_vm(module, vm_name, vm_uuid, si)
        set_permissions(
            module, vm, si, users,
            propagate, role_id,
            group, domain, reset)
    elif action == 'restart':
        vm = find_vm(module, vm_name, vm_uuid, si)
        restart_vm(module, vm, vm_name)
    elif action == 'snapshot':
        vm = find_vm(module, vm_name, vm_uuid, si)
        snapshot_vm(module, vm, vm_name, si, ss_name, ss_memory)
    elif action == 'revert_snapshot':
        vm = find_vm(module, vm_name, vm_uuid, si)
        revert_snapshot(module, vm, vm_name, ss_name)
    elif action == 'delete_snapshot':
        vm = find_vm(module, vm_name, vm_uuid, si)
        delete_snapshot(module, vm, vm_name, si, ss_name)
    elif action == 'shutdown':
        vm = find_vm(module, vm_name, vm_uuid, si)
        shutdown_vm(module, vm, vm_name)
    elif action == 'relocate_vm':
        vm = find_vm(module, vm_name, vm_uuid, si)
        relocate_vm(module, si, vm, resource_pool, cluster_name, vm_folder)
    elif action == 'clone':
        template = get_obj(content, [vim.VirtualMachine], template)
        clone_vm(
            module, si, vm_name,
            template, dns_list, suffix_list,
            datacenter_name, cluster_name,
            datastore, domain_name,
            num_cpus, memory_mb, vm_disk,
            vm_folder, vnics, vm_uuid, os_family,
            login_password, full_name, org_name, resource_pool=resource_pool)
    elif action == 'delete':
        vm = find_vm(module, vm_name, vm_uuid, si)
        delete_vm(module, vm, vm_name)
    elif action == 'upgrade_tools':
        vm = find_vm(module, vm_name, vm_uuid, si)
        upgrade_tools(module, vm)
    elif action == 'reconfigure':
        vm = find_vm(module, vm_name, vm_uuid, si)
        reconfigure_vm(module, vm, vm_name, num_cpus, memory_mb, vm_disk)
    elif action == 'gather_facts':
        vm = find_vm(module, vm_name, vm_uuid, si)
        facts = gather_facts(vm)
        if facts:
            changed = False
            module.exit_json(changed=False, ansible_facts=facts)
    elif action == 'change_uuid':
        vm = get_obj(content, [vim.VirtualMachine], vm_name)
        change_uuid(module, vm, vm_name, vm_uuid)
    else:
        module.fail_json(msg='%s is not a supported action' % action)

    atexit.register(Disconnect, si)


def delete_snapshot(module, vm, vm_name, si, ss_name):
    """ delete a snapshot from a VM """
    changed = False
    changes = []

    if ss_name == 'all':
        task = vm.RemoveAllSnapshots_Task()
        wait_for_task(module, task)
        changes.append("all snapshots removed from VM %s" % vm_name)
        changed = True
    else:
        # find mor of ss_name
        try:
            ss_list = list(vm.snapshot.rootSnapshotList)
        except AttributeError:
            module.exit_json(changed=False)
        found = []
        ss_mob = False
        while ss_list:
            snapshot = ss_list.pop()
            if len(snapshot.childSnapshotList) > 0:
                for child in snapshot.childSnapshotList:
                    ss_list.append(child)
            found.append(snapshot)

        for snapshot in found:
            if snapshot.name == ss_name:
                ss_mob = snapshot.snapshot
                ss_mob.RemoveSnapshot_Task(removeChildren=False)
                changes.append("removed %s from %s" % (ss_name, vm_name))
                changed = True

    if changed:
        module.exit_json(changed=True, changes=changes)
    else:
        module.exit_json(changed=False)


def snapshot_vm(module, vm, vm_name, si, ss_name, ss_memory):
    """ take a snapshot of a VM """
    changed = False
    changes = []

    if not ss_name:
        ss_name = str(datetime.datetime.now())

    task = vm.CreateSnapshot_Task(name=ss_name, memory=ss_memory, quiesce=False)
    wait_for_task(module, task)

    changes.append("snapshot %s taken on %s" % (ss_name, vm_name))

    module.exit_json(changed=True, changes=changes)


def find_vm(module, vm_name, vm_uuid, si):
    """ if vm_uuid find vm by uuid, else, by name """
    content = si.RetrieveContent()
    if vm_uuid:
        vm = get_vm_by_uuid(module, vm_uuid, si)
    else:
        vm = get_obj(content, [vim.VirtualMachine], vm_name)

    if not vm:
        module.fail_json(msg='vm %s does not exist' % vm_name)

    return vm


def get_vm_by_uuid(module, vm_uuid, si):
    """ Returns a vms MOR searching by UUID (BIOS)"""
    vm = si.content.searchIndex.FindByUuid(None, vm_uuid, True)
    if not vm:
        module.fail_json(msg='VM does not exist')

    return vm


def power_off_vm(module, vm):
    """ Powers off a VM"""
    task = vm.PowerOffVM_Task()
    wait_for_task(module, task)


def power_on_vm(module, vm):
    """ Powers on a VM"""
    task = vm.PowerOnVM_Task()
    wait_for_task(module, task)


def shutdown_and_wait(module, vm):
    """
    Graceful shutdown of a VM
    Waits for power state before returning
    """
    wait_timer = 0
    # if the power state is powered on, but is booting
    # here we wait for the tools to initialize
    while vm.guest.toolsRunningStatus != 'guestToolsRunning':
        wait_timer += 1
        time.sleep(2)
        if wait_timer > 90:
            module.fail_json(msg='gave up waiting for tools to start')

    # here we shutdown the VM
    vm.ShutdownGuest()
    # wait for the power state to be poweredOff
    wait_timer = 0
    while vm.summary.runtime.powerState != 'poweredOff':
        wait_timer += 1
        time.sleep(2)
        if wait_timer > 60:
            module.fail_json(msg='gave up waiting for VM to shutdown')


def change_uuid(module, vm, vm_name, vm_uuid):
    """re-key a VM with UUID from the database"""
    changes = []
    spec = vim.vm.ConfigSpec()
    current_vm_uuid = vm.config.uuid

    if current_vm_uuid != vm_uuid:
        changes.append('re-keying %s with %s' % (vm_name, vm_uuid))
        spec.uuid = vm_uuid
    else:
        module.exit_json(changd=False)

    if changes:
        task = vm.ReconfigVM_Task(spec=spec)
        wait_for_task(module, task)
        module.exit_json(changed=True, changes=changes)
    else:
        module.exit_json(changed=False)


def reconfigure_vm(module, vm, vm_name, num_cpus, memory_mb, vm_disk):
    """
    reconfigures a VMs CPU, Memory, and Disk
    """
    changes = []
    dev_changes = None

    power_state = vm.summary.runtime.powerState

    if num_cpus:
        cpu_changes = reconfigure_vm_cpu(module, vm, num_cpus)
        if cpu_changes:
            for change in cpu_changes:
                changes.append(change)

    if memory_mb:
        memory_changes = reconfigure_vm_memory(module, vm, memory_mb)
        if memory_changes:
            for change in memory_changes:
                changes.append(change)

    if vm_disk:
        disk_changes = reconfigure_vm_disk(module, vm, vm_disk)
        if disk_changes:
            for change in disk_changes:
                changes.append(change)

    if changes:
        if vm.summary.runtime.powerState != power_state:
            changes.append('powering on %s' % vm_name)
            power_on_vm(module, vm)
        module.exit_json(changed=True, changes=changes)
    else:
        module.exit_json(changed=False)


def reconfigure_vm_cpu(module, vm, num_cpus):
    changes = []
    spec = vim.vm.ConfigSpec()
    current_cpu = vm.config.hardware.numCPU

    # Reconfigure CPU
    if num_cpus is not None and int(num_cpus) != int(current_cpu):
        if int(num_cpus) > int(current_cpu):
            if not vm.config.cpuHotAddEnabled:
                # when hotadd isn't enabled we need to make sure the VM is off
                # attempt to do this gracefully
                if vm.summary.runtime.powerState == 'poweredOn':
                    shutdown_and_wait(module, vm)
        elif int(num_cpus) < int(current_cpu):
            if not vm.config.cpuHotRemoveEnabled:
                if vm.summary.runtime.powerState == 'poweredOn':
                    shutdown_and_wait(module, vm)
        # set the numCPUs in the spec to the proposed number
        spec.numCPUs = int(num_cpus)
        cpu_diff = int(num_cpus) - int(current_cpu)
        # todo make this message more friendly
        changes.append('cpu difference %s' % cpu_diff)

    if changes:
        task = vm.ReconfigVM_Task(spec=spec)
        wait_for_task(module, task)

    return changes


def reconfigure_vm_memory(module, vm, memory_mb):
    changes = []
    current_memory = vm.config.hardware.memoryMB
    spec = vim.vm.ConfigSpec()
    vm_name = vm.config.name

    # Reconfigure Memory
    if memory_mb is not None and int(memory_mb) != int(current_memory):
        if int(memory_mb) > int(current_memory):
            if not vm.config.memoryHotAddEnabled:
                if vm.summary.runtime.powerState == 'poweredOn':
                    changes.append('no memoryHotAdd shutting down %s' % vm_name)
                    shutdown_and_wait(module, vm)
            else:
                memory_diff_mb = int(memory_mb) - int(current_memory)
                if int(memory_mb) > vm.config.hotPlugMemoryLimit:
                    if vm.summary.runtime.powerState == 'poweredOn':
                        changes.append(
                            'memory exceeds %s shutting down %s'
                            % (vm.config.hotPlugMemoryLimit, vm_name))
                        shutdown_and_wait(module, vm)
        if int(memory_mb) < int(current_memory):
            if vm.summary.runtime.powerState == 'poweredOn':
                changes.append('reducing memory. shutting down %s' % vm_name)
                shutdown_and_wait(module, vm)

        spec.memoryMB = int(memory_mb)
        memory_diff_mb = int(memory_mb) - int(current_memory)
        changes.append('memory difference is %s' % memory_diff_mb)

    if changes:
        task = vm.ReconfigVM_Task(spec=spec)
        wait_for_task(module, task)

    return changes


def reconfigure_vm_disk(module, vm, vm_disk):
    # Reconfigure Disks
    # prepare vm_disk dict for use with spec
    disk_num = 0
    changes = []
    dev_changes = []
    spec = vim.vm.ConfigSpec()

    # ensure the keys are int for sorting
    vm_disk = {int(k): v for k, v in vm_disk.items()}

    # unit_number, or scsi num
    unit_number = 0

    # loop over items in vm_disk dict.
    # find any drives that already exist and expand if needed
    for disk in sorted(vm_disk.iterkeys()):
        for dev in vm.config.hardware.device:
            if hasattr(dev.backing, 'fileName'):
                disk_label = 'Hard disk ' + str(disk)
                if dev.deviceInfo.label == disk_label:
                    unit_number += 1
                    # unitNumber 7 used by controller
                    if unit_number == 7:
                        unit_number += 1
                    capacity_in_kb = dev.capacityInKB
                    disk_size_gb = int(vm_disk[disk]['size_gb'])
                    new_disk_kb = int(disk_size_gb) * 1024 * 1024
                    # if proposed disk is larger than existing disk
                    # we expand it here
                    if new_disk_kb > capacity_in_kb:
                        disk_spec = vim.vm.device.VirtualDeviceSpec()
                        disk_spec.operation = \
                            vim.vm.device.VirtualDeviceSpec.Operation.edit
                        disk_spec.device = vim.vm.device.VirtualDisk()
                        disk_spec.device.key = dev.key
                        disk_spec.device.backing = \
                            vim.vm.device.VirtualDisk.FlatVer2BackingInfo()
                        disk_spec.device.backing.fileName = \
                            dev.backing.fileName
                        disk_spec.device.backing.diskMode = \
                            dev.backing.diskMode
                        disk_spec.device.controllerKey = dev.controllerKey
                        disk_spec.device.unitNumber = dev.unitNumber
                        disk_spec.device.capacityInKB = new_disk_kb
                        dev_changes.append(disk_spec)
                        changes.append(
                            '%s has been expanded to %sGB'
                            % (disk_label, vm_disk[disk]['size_gb']))
                    del vm_disk[disk]

    # any remaining items in the dict weren't found on the VM. add them here
    for disk in sorted(vm_disk.iterkeys()):
        disk_label = 'Hard disk ' + str(disk)
        new_disk_kb = int(vm_disk[disk]['size_gb']) * 1024 * 1024
        disk_spec = vim.vm.device.VirtualDeviceSpec()
        disk_spec.fileOperation = "create"
        disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
        disk_spec.device = vim.vm.device.VirtualDisk()
        disk_spec.device.backing = \
            vim.vm.device.VirtualDisk.FlatVer2BackingInfo()
        if vm_disk[disk]['type'] == 'thin':
            disk_spec.device.backing.thinProvisioned = True
        disk_spec.device.backing.diskMode = 'persistent'
        disk_spec.device.unitNumber = unit_number
        disk_spec.device.capacityInKB = new_disk_kb
        disk_spec.device.controllerKey = 1000
        dev_changes.append(disk_spec)
        unit_number += 1
        # unitNumber 7 used by controller
        if unit_number == 7:
            unit_number += 1
        changes.append('adding %s to VM' % disk_label)

    if dev_changes:
        spec.deviceChange = dev_changes
        task = vm.ReconfigVM_Task(spec=spec)
        wait_for_task(module, task)

    return changes


def get_obj(content, vimtype, name, **kwargs):
    """
    Returns an object based on it's vimtype and name
    """
    obj = None
    obj_container = kwargs.get('container', content.rootFolder)
    container = content.viewManager.CreateContainerView(
        obj_container, vimtype, True)
    for c in container.view:
        if c.name == name:
            obj = c
            break
    return obj


def get_disk_layout(vm):
    """ returns a dict of disks on a VM """

    vm_disk = []
    for dev in vm.config.hardware.device:
        if 'disk' in dev.deviceInfo.label and hasattr(dev.backing, 'fileName'):
            disk_label = dev.deviceInfo.label
            disk_layout = {}
            disk_layout[disk_label] = {}
            thin_provisioned = dev.backing.thinProvisioned
            capacity_in_kb = dev.capacityInKB
            capacity_in_gb = capacity_in_kb / 1024 / 1024
            if thin_provisioned:
                disk_layout[disk_label]['disk_type'] = 'thin'
            else:
                disk_layout[disk_label]['disk_type'] = 'thick'
            disk_layout[disk_label]['size_gb'] = capacity_in_gb
            vm_disk.append(disk_layout)

    return vm_disk


def gather_facts(vm):
    """
    set ansible_facts based on a VMs configuration
    """
    snapshots = []
    snapshot_list = []
    ips = []
    try:
        snapshot_list = vm.snapshot.rootSnapshotList
    except AttributeError:
        pass
    for snapshot in snapshot_list:
        snapshots.append(snapshot.name)
    guest_primary_ipaddress = vm.guest.ipAddress
    guest_family = vm.guest.guestFamily
    memory_mb = vm.summary.config.memorySizeMB
    guest_id = vm.guest.guestId
    nics = vm.guest.net
    for nic in nics:
        for addr in nic.ipAddress:
            ips.append(addr)
    memory_gb = memory_mb / 1024
    num_cpus = vm.summary.config.numCpu
    vm_disk_layout = get_disk_layout(vm)

    # compute a sum of disk size_gb items
    total_capacity_in_gb = 0
    for disk in vm_disk_layout:
        for item in disk:
            total_capacity_in_gb += int(disk[item]['size_gb'])

    facts = {}
    facts['power_state'] = vm.summary.runtime.powerState
    facts['vmmoid'] = vm._moId
    facts['vm_uuid'] = vm.config.uuid
    facts['vm_name'] = vm.config.name
    facts['vm_folder'] = str(vm.parent.name)
    facts['resource_pool'] = vm.resourcePool.name
    if guest_primary_ipaddress:
        facts['guest_primary_ipaddress'] = guest_primary_ipaddress
    facts['instance_uuid'] = vm.config.instanceUuid
    if vm_disk_layout:
        facts['disk_layout'] = vm_disk_layout
    if snapshots:
        facts['snapshots'] = snapshots
    if guest_family:
        facts['guest_family'] = guest_family
    facts['memory_mb'] = memory_mb
    facts['memory_gb'] = memory_gb
    facts['num_cpus'] = num_cpus
    if ips:
        facts['ips'] = ips
    facts['disk_capacity_gb'] = total_capacity_in_gb
    facts['vmware_guest_id'] = guest_id

    return facts


def get_vnic_count(vm):
    """"returns the number of vnics a VM has"""
    count = 0
    for dev in vm.config.hardware.device:
        if isinstance(dev, (vim.vm.device.VirtualVmxnet3,
                            vim.vm.device.VirtualE1000,
                            vim.vm.device.VirtualVmxnet2,
                            vim.vm.device.VirtualPCNet32,
                            vim.vm.device.VirtualE1000e,
                            vim.vm.device.VirtualVmxnet)):
            count += 1

    return count

def relocate_vm(
        module, si, vm, resource_pool, cluster_name, vm_folder):
        """
        relocates a vm to the passed resource_pool, and cluster_name
        """
        content = si.RetrieveContent()
        changes = []
        changed = False

        cluster = get_obj(content, [vim.ClusterComputeResource], cluster_name)
        if not cluster:
            module.fail_json(msg='can not locate cluster')

        if resource_pool:
            resource_pool = get_obj(content, [vim.ResourcePool], resource_pool, container=cluster)
        else:
            resource_pool = cluster.resourcePool

        if vm_folder:
            if vm_folder != vm.parent.name:
                dest_folder = get_obj(content, [vim.Folder], vm_folder)
                if not dest_folder:
                    module.fail_json(msg='% Folder does not exist' % vm_folder)
                items_to_move = [vm]
                dest_folder.MoveIntoFolder_Task(items_to_move)
                changed = True
                changes.append('VM %s moved into %s folder' % (vm.config.name, vm_folder))

        relospec = vim.vm.RelocateSpec()
        # relospec.datastore = datastore
        relospec.pool = resource_pool

        if vm.resourcePool != resource_pool:
            task = vm.RelocateVM_Task(relospec)
            relocated_vm = wait_for_task(module, task)
            changed = True
            changes.append('VM relocated to %s RP' % (resource_pool.name))
        else:
            changed = False

        module.exit_json(changed=changed, changes=changes)


def get_datastores_in_cluster(si, datastore_cluster):
        """
        returns a list of datastores in datastore cluster
        """
        datastores = []
        content = si.RetrieveContent()
        datastore_cluster_obj = get_obj(content, [vim.StoragePod], datastore_cluster)
        if datastore_cluster_obj:
            for datastore in datastore_cluster_obj.childEntity:
                datastores.append(datastore)

        return datastores


def clone_vm(
        module, si, vm_name, template, dns_list,
        suffix_list, datacenter_name, cluster_name,
        datastore, domain_name, num_cpus, memory_mb,
        vm_disk, vm_folder, vnics, vm_uuid,
        os_family, login_password, full_name, org_name, **kwargs):
    """
    Clones a VM from another VM or template
    does guest customizations on said VM
    reconfigures VMs disk config
    """
    resource_pool = kwargs.get('resource_pool', None)
    changed = False
    changes = []
    content = si.RetrieveContent()
    datacenter = get_obj(content, [vim.Datacenter], datacenter_name)
    cluster = get_obj(content, [vim.ClusterComputeResource], cluster_name)

    datastores_in_cluster = get_datastores_in_cluster(si, datastore)
    if datastores_in_cluster:
        datastore_obj = random.choice(datastores_in_cluster)
    else:
        datastore_obj = get_obj(content, [vim.Datastore], datastore, container=datacenter)

    if vm_folder:
        destfolder = get_obj(content, [vim.Folder], vm_folder, container=datacenter)
    else:
        destfolder = datacenter.vmFolder

    if resource_pool:
        resource_pool = get_obj(content, [vim.ResourcePool], resource_pool, container=cluster)
    else:
        resource_pool = cluster.resourcePool

    if not datastore_obj:
        module.fail_json(msg='Datastore %s not found' % datastore)

    if not destfolder:
        module.fail_json(msg='Could not target a folder')

    # relocation spec
    relospec = vim.vm.RelocateSpec()
    relospec.datastore = datastore_obj
    relospec.pool = resource_pool

    devices = []
    adaptermaps = []

    vm_nic_count = get_vnic_count(template)
    nic_num = 0

    for nic in vnics:
        nic_num += 1

        network_type = vnics[nic].get('network_type', 'dvs')
        if network_type != 'dvs' and network_type != 'standard':
            changes.append('defaulting to dvs network %s is an unsupported network_type' % (network_type))
            network_type = 'dvs'

        vswitch_name = vnics[nic].get('vswitch', None)
        ip = vnics[nic].get('ip', None)
        netmask = vnics[nic].get('netmask', None)
        gateway = vnics[nic].get('gateway', None)
        ipv6_addr = vnics[nic].get('ipv6_addr', None)
        ipv6_prefix_length = vnics[nic].get('ipv6_prefix_length', None)
        ipv6_defaultgw = vnics[nic].get('ipv6_defaultgw', None)

        nic = vim.vm.device.VirtualDeviceSpec()
        if nic_num > vm_nic_count:
            nic.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
        else:
            nic.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
        nic.device = vim.vm.device.VirtualVmxnet3()
        nic.device.wakeOnLanEnabled = True
        nic.device.addressType = 'assigned'
        nic.device.key = 4000
        nic.device.deviceInfo = vim.Description()
        if network_type == 'dvs':
            pg_obj = get_obj(
                content,
                [vim.dvs.DistributedVirtualPortgroup],
                vswitch_name)
            if not pg_obj:
                module.fail_json(msg='portgroup %s does not exist' % (vswitch_name))
            dvs_port_connection = vim.dvs.PortConnection()
            dvs_port_connection.portgroupKey = pg_obj.key
            dvs_port_connection.switchUuid = \
                pg_obj.config.distributedVirtualSwitch.uuid
            nic.device.backing = \
                vim.vm.device.VirtualEthernetCard.DistributedVirtualPortBackingInfo()
            nic.device.backing.port = dvs_port_connection
        if network_type == 'standard':
            nic.device.deviceInfo.summary = vswitch_name
            nic.device.backing = \
                vim.vm.device.VirtualEthernetCard.NetworkBackingInfo()
            pg_obj = get_obj(content, [vim.Network], vswitch_name)

            if not pg_obj:
                module.fail_json(msg='portgroup %s does not exist' % (vswitch_name))

            nic.device.backing.network = pg_obj
            nic.device.backing.deviceName = vswitch_name
            nic.device.backing.useAutoDetect = False
            nic.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
            nic.device.connectable.startConnected = True
            nic.device.connectable.allowGuestControl = True

        devices.append(nic)

        # network guest_map
        guest_map = vim.vm.customization.AdapterMapping()
        guest_map.adapter = vim.vm.customization.IPSettings()
        guest_map.adapter.ip = vim.vm.customization.FixedIp()
        if ip:
            guest_map.adapter.ip = vim.vm.customization.FixedIp()
            guest_map.adapter.ip.ipAddress = str(ip)
        else:
            guest_map.adapter.subnetMask = str(netmask)
        if netmask:
            guest_map.adapter.subnetMask = str(netmask)
        if ipv6_addr:
            guest_map.adapter.ipV6Spec = \
                vim.vm.customization.IPSettings.IpV6AddressSpec()
            guest_map.adapter.ipV6Spec.ip = [vim.vm.customization.FixedIpV6()]
            guest_map.adapter.ipV6Spec.ip[0].ipAddress = ipv6_addr
        if ipv6_prefix_length:
            guest_map.adapter.ipV6Spec.ip[0].subnetMask = \
                int(ipv6_prefix_length)
        if ipv6_defaultgw:
            guest_map.adapter.ipV6Spec.gateway = ipv6_defaultgw
        if gateway:
            guest_map.adapter.gateway = gateway

        adaptermaps.append(guest_map)

    # vm configuration
    vmconf = vim.vm.ConfigSpec()
    vmconf.numCPUs = int(num_cpus)
    vmconf.memoryMB = int(memory_mb)
    vmconf.cpuHotAddEnabled = False
    vmconf.annotation = vm_uuid
    vmconf.memoryHotAddEnabled = False
    vmconf.deviceChange = devices
    if vm_uuid:
        vmconf.uuid = vm_uuid

    globalip = vim.vm.customization.GlobalIPSettings()
    globalip.dnsServerList = [d.encode('utf-8') for d in dns_list]
    globalip.dnsSuffixList = suffix_list

    # set domain and host names
    host_name = vm_name
    if len(vm_name.split('.')) > 1:
        host_name = vm_name.split('.')[0]
        host_tuple = vm_name.split('.')
        # rm host_name portion of domain_name, apppend
        # domain_name to it
        host_tuple.pop(0)
        domain_name = '.'.join(host_tuple) + "." + domain_name

    if os_family == 'linux':
        ident = vim.vm.customization.LinuxPrep()
        ident.domain = domain_name
        ident.hostName = vim.vm.customization.FixedName()
        ident.hostName.name = host_name
    if os_family == 'windows':
        gui_unattended = vim.vm.customization.GuiUnattended()
        gui_unattended.timeZone = 35
        gui_unattended.autoLogon = False
        gui_unattended.password = vim.vm.customization.Password()
        gui_unattended.password.value = login_password
        gui_unattended.password.plainText = True

        computer_name = vim.vm.customization.VirtualMachineNameGenerator()

        user_data = vim.vm.customization.UserData()
        user_data.fullName = full_name
        user_data.orgName = org_name
        user_data.computerName = computer_name

        identification = vim.vm.customization.Identification()
        identification.joinWorkgroup = 'WORKGROUP'

        ident = vim.vm.customization.Sysprep()
        ident.guiUnattended = gui_unattended
        ident.userData = user_data
        ident.identification = identification

    customspec = vim.vm.customization.Specification()
    customspec.nicSettingMap = adaptermaps
    customspec.globalIPSettings = globalip
    customspec.identity = ident

    clonespec = vim.vm.CloneSpec()
    clonespec.location = relospec
    clonespec.config = vmconf
    clonespec.customization = customspec
    clonespec.powerOn = True
    clonespec.template = False

    task = template.Clone(folder=destfolder, name=vm_name, spec=clonespec)
    new_vm = wait_for_task(module, task)

    changed = True
    changes.append('vm %s has been created' % vm_name)

    if vm_disk:
        disk_changes = reconfigure_vm_disk(module, new_vm, vm_disk)
        if disk_changes:
            for change in disk_changes:
                changes.append(change)

    if changes:
        module.exit_json(
            changed=True, changes=changes,
            ansible_facts=gather_facts(new_vm))



def upgrade_tools(module, vm):
    """
    Checks a VM for vmware-tools upgrade
    """
    wait_timer = 0
    changes = []
    # save VM's state, power on if needed
    power_state = vm.summary.runtime.powerState
    if power_state == 'poweredOff' or power_state == 'suspended':
        task = vm.PowerOnVM_Task()
        wait_for_task(module, task)
        changes.append("VM powered on to install tools")

    # are tools running?
    while vm.guest.toolsRunningStatus != 'guestToolsRunning':
        wait_timer += 1
        time.sleep(2)
        if wait_timer > 40:
            module.fail_json(msg='gave up waiting for tools to start')

    # get vm tools status
    tools_status = vm.guest.toolsVersionStatus2
    if tools_status == 'guestToolsSupportedOld' or tools_status == 'guestToolsNeedUpgrade':
        task = vm.UpgradeTools_Task()
        wait_for_task(module, task)
        changes.append('vmware-tools upgraded')
    elif tools_status == 'guestToolsCurrent' or tools_status == 'guestToolsSupportedNew' or tools_status == 'guestToolsUnmanaged':
        module.exit_json(changed=False)
    elif tools_status == 'guestToolsTooNew':
        module.fail_json(msg='tools too new for this host')
    elif tools_status == 'guestToolsBlacklisted':
        module.fail_json(msg='tools are blacklisted for this host')
    elif tools_status == 'guestToolsNotInstalled':
        module.fail_json(msg='tools are not installed')
    elif tools_status == 'guestToolsTooOld':
        module.fail_json(msg='tools too old. install manually')
    else:
        module.fail_json(msg='tools upgrade failed')

    # if the vm was powered off before upgrading tools. shutdown VM here
    if power_state != vm.summary.runtime.powerState:
        vm.ShutdownGuest()
        changes.append("VM Shutdown")

    if changes:
        module.exit_json(changed=True, changes=changes)


def set_permissions(
        module, vm, si, users,
        propagate, role_id, group,
        domain, reset):
    """
    Grants a user a specific role_id to a user on a VM object
    """
    changed = False
    changes = []
    auth_mgr = si.content.authorizationManager
    auth_perm = vim.AuthorizationManager.Permission
    perms_list = []
    for user in users:
        # if domain is set, append to user before running SetEntityPermissions
        if domain:
            user = domain + '\\' + user

        perms = auth_perm(
            group=group, principal=user,
            propagate=propagate, roleId=role_id)
        perms_list.append(perms)
        changes.append(user)

    if reset:
        try:
            auth_mgr.ResetEntityPermissions(vm, perms_list)
            changed = True
        # todo more error catching here
        except vim.fault.UserNotFound:
            module.fail_json(msg='User %s could not be found' % user)
    else:
        try:
            auth_mgr.SetEntityPermissions(vm, perms_list)
        except vim.fault.UserNotFound:
            module.fail_json(msg='User %s could not be found' % user)

    if changed:
        module.exit_json(changed=True, changes=changes)


def restart_vm(module, vm, vm_name):
    """
    Restart a VM
    """
    changes = []
    wait_timer = 0
    # power on VM if it's powered off
    if (vm.summary.runtime.powerState == 'poweredOff') or (vm.summary.runtime.powerState == 'suspended'):
        power_on_vm(module, vm)
        changes.append('vm %s has been powered on' % vm_name)
        module.exit_json(changed=True, changes=changes)

    # if tools aren't running, give them a chance to start
    while vm.guest.toolsRunningStatus != 'guestToolsRunning':
        wait_timer += 1
        time.sleep(2)
        if wait_timer > 20:
            module.fail_json(msg='gave up waiting for tools to start')

    # finally, reboot the VM
    try:
        vm.RebootGuest()
        changes.append('%s has been restarted' % vm_name)
    except vim.fault.ToolsUnavailable:
        module.fail_json(msg='vmware-tools aren\'t running on %s' % vm_name)
    if changes:
        module.exit_json(changed=True, changes=changes)


def shutdown_vm(module, vm, vm_name):
    """
    Shuts down a VM
    """
    # changed = False
    changes = []

    try:
        vm.ShutdownGuest()
        # changed = True
        changes.append('%s has been shut down' % vm_name)
    except:
        module.fail_json(msg='failed to shutdown VM, %s' % vm_name)

    if changes:
        module.exit_json(changed=True, changes=changes)


def wait_for_task(module, task):
    """
    Wait for a task to complete
    """
    # set generic message
    error_msg = "an error occurred while waiting for task to complete"
    task_done = False
    while not task_done:
        if task.info.state == 'success':
            return task.info.result

        if task.info.state == 'error':
            if isinstance(task.info.error, vim.fault.DuplicateName):
                error_msg = "an object with the name %s already exists" % task.info.error.name
            elif isinstance(task.info.error, vim.fault.FileFault):
                error_msg = "file caused clone error. is CBT enabled?"
            module.fail_json(
                msg=error_msg)



def delete_vm(module, vm, vm_name):
    """
    Delete a VM based on it's name and BIOS uuid
    """
    changes = []
    changed = False
    if vm_name == vm.config.name:
        if vm.runtime.powerState != 'poweredOff':
            task = vm.PowerOffVM_Task()
            wait_for_task(module, task)
        task = vm.Destroy_Task()
        wait_for_task(module, task)
        changed = True
        changes.append('VM %s has been deleted' % vm_name)
    else:
        module.fail_json(msg='VM name does not match UUID')

    if changed:
        module.exit_json(changed=True, changes=changes)
    else:
        module.fail_json(msg='failed to delete VM %s' % vm_name)


def revert_snapshot(module, vm, vm_name, ss_name):
    """
    Revert to a named snapshot or if a name isn't defined
    revert to the most recent snapshot
    """
    changed = False
    changes = []

    # if ss_name is defined, find named snapshot, and revert it
    if ss_name:
        found = []
        ss_mob = False
        ss_list = list(vm.snapshot.rootSnapshotList)
        while ss_list:
            snapshot = ss_list.pop()
            if len(snapshot.childSnapshotList) > 0:
                for child in snapshot.childSnapshotList:
                    ss_list.append(child)
            found.append(snapshot)

        for snapshot in found:
            if snapshot.name == ss_name:
                ss_mob = snapshot.snapshot
                break

        if ss_mob:
            try:
                task = ss_mob.RevertToSnapshot_Task()
                wait_for_task(module, task)
                changed = True
                changes.append('snapshot %s has been reverted' % ss_name)
            except:
                module.fail_json(msg='revert snapshot on %s failed' % vm_name)
        else:
            module.fail_json(msg='can not find snapshot %s' % ss_name)
    # if ss_name isn't defined, try revert to current snap
    else:
        try:
            task = vm.RevertToCurrentSnapshot_Task()
            wait_for_task(module, task)
            changed = True
            changes.append('reverted to current snapshot on %s' % vm_name)
        except:
            module.fail_json(msg='revert to snapshot on %s failed' % vm_name)

    # If vm gets powered off, power it back on
    power_state = vm.summary.runtime.powerState
    if power_state != 'poweredOn':
        try:
            task = vm.PowerOnVM_Task()
            wait_for_task(module, task)
            changed = True
            changes.append('VM %s powered on' % vm_name)
        except:
            module.fail_json(msg='can not power on VM, %s' % vm_name)

    if changed:
        module.exit_json(changed=True, changes=changes)

from ansible.module_utils.basic import *
main()

#!/usr/bin/env python

# Copyright (c) 2014, ViaSat Inc.
#
# All rights reserved.
# Redistribution and use in source and binary forms,
# with or without modification, are permitted provided
# that the following conditions are met:
#
# Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer. Redistributions
# in binary form must reproduce the above copyright notice, this list of
# conditions and the following disclaimer in the documentation and/or
# other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, PUNITIVE, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
# NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE

try:
    import json
except ImportError:
    import simplejson as json

import re
import os
import ast
import ssl
import time
import atexit
import datetime
import copy

try:
    from pyVim.connect import SmartConnect, Disconnect
    from pyVmomi import vim, vmodl
except ImportError:
    print("failed=True msg='pyVmomi is required to run this module'")

DOCUMENTATION = '''
---
module: vsphere
short_description: Manage vSphere VMs
description:
    - Provides an interface to manage the lifecycle of a VM. Can create, clone, delete, power on and off, and snapshot the VMs.
version_added: "1.5"
options:
    host:
        description:
            - Address to connect to the vSphere API.
        required: True
        default: null
    login:
        description:
            - Username to login to vSphere API with.
        required: True
        default: null
    password:
        description:
            - Password that will authenticate to vSphere API with.
        required: True
        default: null
    timeout:
        description:
            - Time to wait for an action to complete
        required: False
        default: 60 seconds
    guest:
        description:
            - A dictionary describing the vm that will be acted on.
              Accepted parameters are
            - name The name of the VM to be acted on. This is required.
            - state The state the VM should be in such as I(running) for
                       powered on or absent for deleted
            - folder The folder the VM should be located in the inventory
            - force If the state is I(shutdown) then the force option will
                       check if vmware tools are installed, and if they are not
                       it will force stop the vm instead of attempting to
                       gracefully shut it down.
            - clone_from Specifies the name of the VM or template to clone
                            this vm from.
            - action A specific action to take on the VM. If this value is I(task)
                        the C(spec) object needs to be populated with details of a
                        task to call on the VM Managed Object. See the vSphere API
                        reference for details on the tasks that can be called on
                        a Virtual Machine reference.
        required: False
        default: null
    snapshot:
        description:
            - A dictionary describing actions that can be done to a VMs
              snapshots. This requires that the guest has been set.
              Accepted parameters are
            - name The name of the snapshot to act on.
            - action The action to take on the snapshot.
                        e.g. create, remove, revert
            - memory When creating a snapshot, whether to include the
                        running memory.
            - quiesce When creating a snapshot, whether to quiesce the
                         file system of the VM.
            - children When removing a snapshot, whether to remove the
                          children snapshots as well.
        required: False
        default: null
    folder:
        description:
            - A dictionary describing actions that can be taken on folders
              in the inventory.
              Accepted parameters are
            - name The name of the folder to act on.
            - state The state the folder should be in. Can be I(present)
                       or I(absent)
            - parent The name of the parent folder to this folder. If no
                        parent is given, this folder defaults to I(Datacenters)
        required: False
        default: null
    guest_operations_manager:
        description:
            - The name of a manager to call. When this option is present
              the C(spec) will be used to call a function on the manager.
        required: False
        choices: [ fileManager, processManager, authManager ]
    put_file:
        description:
            - Used with the C(guest_operations_manager) fileManager option.
              If you want to send a file the guest operating system, this value
              will specify that source file. Can be a relative or absolute path.
            - Used in conjunction with the C(spec) to fill out the options for the
              InitiateFileTransferToGuest task on the fileManager in vSphere.
    get_file:
        description:
            - Used with the C(guest_operations_manager) fileManager option.
              If you want to get a file from guest operating system, this value
              will specify that source file. Can be a relative or absolute path.
            - Used in conjunction with the C(spec) to fill out the options for the
              InitiateFileTransferFromGuest task on the fileManager in vSphere.
    spec:
        description:
            - The spec object is a dictionary that will be converted to the
              correct vsphere object during processing of the task. The spec
              object has two top level parameters
            - type The type of spec ( such as VirtualMachineCloneSpec )
                      In some cases this could also be the name of a function
                      that will be called
            - value A representation of the values that fill out the spec
                       object. In the case of the spec being used to specify
                       a function being called, the values should be the
                       parameters that get passed to the function.
            - 'In order to fill spec objects with other spec objects, the values
              will be put through a recursive update, that will convert any key
              that is an attribute of the C(vim) module of C(pyVmomi). The
              update process can even substitute Managed Object References
              through the special syntax. C( { "ManagedObjectReference" : { "type": "MOR TYPE", "name" : "MOR NAME" } } )
          Sometimes managed objects are named the same across multiple parent objects.
          For instance you may have two clusters setup within a datacenter each with
          a resource pool named Resources. In order to match the correct resource pool
          you can add a limit to the ManagedObjectReference definition so that the MOR
          will be looked up relative to another Managed object.
              See the Clone VM example for a fairly ful example including an example of a
          managed object reference with a limit.'
        required: False
        default: null
requirements: [ "pyVmomi", "requests" ]
author: Tony Kinsley
'''

EXAMPLES = '''
# Note: None of these examples set the login information
# ( host, login, password ). It is assumed those are also present.
  tasks:
    - name: Test Shutdown
      local_action:
        module: vsphere
        guest:
            name: guest_name
            force: true
            state: shutdown
    - name: Test Create Snapshot
      local_action:
        module: vsphere
        guest:
            name: guest_name
            state: running
        snapshot:
          name: test
          memory: False
          action: create
    - name: Test Revert Snapshot
      local_action:
        module: vsphere
        guest:
            name: guest_name
            state: running
        snapshot:
          name: baseline
          action: revert
    - name: Test Remove Snapshot
      local_action:
        module: vsphere
        guest:
            name: guest_name
            state: running
        snapshot:
          name: test
          children: False
          action: remove
    - name: Test Power On
      local_action:
        module: vsphere
        guest:
            name: guest_name
            state: running
    - name: Rename VM
      local_action:
        module: vsphere
        guest:
          name: guest_name
          new_name: guest_new_name
          action: rename
    - name: Clone VM
      local_action:
        module: vsphere
        host: "{{ vcenter_host }}"
        login: "{{ vcenter_login }}"
        password: "{{ vcenter_password }}"
        timeout: 60
        guest:
          name: "{{ deleteme }}"
          state: present
          folder: "{{ folder }}"
          clone_from: base-tmpl
        spec:
          type: VirtualMachineCloneSpec
          value:
            config:
              VirtualMachineConfigSpec:
                name: "{{ deleteme }}"
                memoryMB: 2048
                numCPUs: 1
                deviceChange: []
            location:
              VirtualMachineRelocateSpec:
                pool:
                  ManagedObjectReference:
                    type: ResourcePool
                    name: Resources
                    limit:
                      type: ComputeResource
                      name: '{{ compute_resource }}'
                host:
                  ManagedObjectReference:
                    type: HostSystem
                    name: '{{ compute_resource }}'
                datastore:
                  ManagedObjectReference:
                    type: Datastore
                    name: '{{ datastore }}'
            powerOn: False
            template: False
    - name: Upgrade Tools
      local_action:
        module: vsphere
        host: "{{ vcenter_host }}"
        login: "{{ vcenter_login }}"
        password: "{{ vcenter_password }}"
        timeout: 60
        guest:
          name: "{{ deleteme }}"
          state: running
          action: upgrade_tools
    - name: install hostname file
      local_action:
        module: vsphere
        host: "{{ vcenter_host }}"
        login: "{{ vcenter_login }}"
        password: "{{ vcenter_password }}"
        timeout: 60
        guest_operations_manager: fileManager
        put_file: /tmp/{{ deleteme }}/hostname
        spec:
          type: InitiateFileTransferToGuest
          value:
            vm:
              ManagedObjectReference:
                type: VirtualMachine
                name: "{{ deleteme }}"
            auth:
              NamePasswordAuthentication:
                username: root
                password: password
            guestFilePath: /etc/hostname
            fileAttributes:
              GuestPosixFileAttributes: {}
            overwrite: True
'''

class VsphereJsonEncoder(json.JSONEncoder):

    def default(self, obj):
        try:
            return vars(obj)
        except TypeError:
            if isinstance(obj, datetime.datetime):
                return str(obj)

        super(VsphereJsonEncoder, self).default(obj)

class Vsphere(object):

    def __init__(self, module):
        self.changed = False
        self.module = module

        self.vsphere_host = module.params.get('host')
        login_username = module.params.get('login')
        login_password = module.params.get('password')
        self.timeout = module.params.get('timeout')
        check_ssl = bool(module.params.get('checkssl'))

        #####################################
        #                                   #
        # SSL cert support for pyvmomi 6.0+ #
        #                                   #
        #####################################


        context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
        context.verify_mode = ssl.CERT_NONE


        if not check_ssl:
            ssl._create_default_https_context = ssl._create_unverified_context

        try:
            self.si = SmartConnect(host = self.vsphere_host, user = login_username, pwd = login_password, sslContext=context)
        except:
            self.module.fail_json(msg = 'Could not connect to host %s' % self.vsphere_host)

        atexit.register(Disconnect, self.si)

    def _wait_task(self, task):
        while (task.info.state != vim.TaskInfo.State.success and task.info.state != vim.TaskInfo.State.error):
            time.sleep(2)

        failed = False
        if task.info.state == vim.TaskInfo.State.success:
            out = '"%s" completed successfully.%s' %(task.info.task,
                ': %s' % task.info.result if task.info.result else '')
        else:
            failed = True
            if task.info.error:
                out = '%s did not complete successfully: %s' %(task.info.task,
                    task.info.error.msg)
            else:
                out = '%s did not complete successfully: with unknown error, state: %s' %(task.info.task,
                                                                        task.info.state)

        return failed, out, task

    def get_container_view(self, vimtype, name = None, recurse = True, limit = None):
        """
        Get vsphere object(s), if name is not None, return the first object found.
    limit will change the root directory to search for the vsphere object from.
        """
        if isinstance(limit, dict):
            limit = self.get_container_view( [getattr(vim, limit['type'])], limit['name'] )
        else:
            limit = self.content.rootFolder

        container = self.content.viewManager.CreateContainerView(limit, vimtype, recurse)
        if name is not None:

            def name_matches(child, name):
                try:
                    return child.name == name
                except vmodl.fault.ManagedObjectNotFound:
                    # This exception can be thrown (e.g. intermittently when creating multiple VMs in parallel)
                    #   because we're trying to get properties of a child which is partway being created or deleted.
                    # Ideally we'd like to check the name in a way which doesn't trigger exceptions, but for now
                    #   we just ignore the exception to prevent it propagating and failing the module.
                    return False

            return [ c for c in container.view if name_matches(c, name)][0]

        return container.view

    def update_spec(self, spec):
        """
        Utility function for taking a dictionary object and converting
        embedded values to vim objects.
        This function updates the dictianary in place, similar to dict.update
        For Example:
            spec = {
                'name' : 'vmname', 'numCPUs' : 1,
                'files' : {
                    'VirtualMachineFileInfo' : { 'vmPathName' : '[datastore]vmname' }
                }
             }
             -->  ( output from ipython )
             {'files': (vim.vm.FileInfo) {
                     dynamicType = <unset>,
                     dynamicProperty = (vmodl.DynamicProperty) [],
                     vmPathName = '[datastore]vmname',
                     snapshotDirectory = <unset>,
                     suspendDirectory = <unset>,
                     logDirectory = <unset>
             },
             'name': 'vmname',
             'numCPUs': 1}
        """
        if not isinstance(spec, dict):
            return spec

        for spec_name, spec_value in spec.iteritems():
            # Ansible returns numbers as unicode
            try:
                spec[spec_name] = int(spec_value)
            except (ValueError,TypeError):
                try:
                    spec[spec_name] = float(spec_value)
                except (ValueError,TypeError):
                    # Ansible returns bool as unicode
                    try:
                        if (spec_value == "True") or (spec_value == "False"):
                            spec[spec_name] = ast.literal_eval(spec_value)
                    except (ValueError,TypeError):
                        pass

            # recursively update the values
            if spec_name == 'ManagedObjectReference':
                try:
                    return self.get_container_view([getattr(vim, spec_value['type'])],
                                                    spec_value['name'],
                                                    limit = spec_value.get('limit', None))
                except IndexError:
                    self.module.fail_json(msg = 'Failed to find %s within %s'
                        %(spec_value['name'], spec_value.get('limit', 'root')))
            if isinstance(spec_value, dict):
                spec[spec_name] = self.update_spec(spec_value)
            if isinstance(spec_value, list):
                spec[spec_name] = [ self.update_spec(v) for v in spec_value ]
            if hasattr(vim, spec_name) and isinstance(spec_value, dict):
                try:
                    return getattr(vim, spec_name)(**spec_value)
                except AttributeError:
                    pass
        return spec

    @property
    def content(self):
        if not hasattr(self, '_content'):
            self._content = self.si.RetrieveContent()
        return self._content

    @property
    def datacenter(self):
        if not hasattr(self, '_datacenter'):
            dc = self.module.params.get('datacenter', None)
            if dc is not None:
                self._datacenter = [ d for d in self.content.rootFolder.childEntity
                                     if d.name == dc][0]
            else:
                self._datacenter = self.content.rootFolder.childEntity[0]

        return self._datacenter

################################################################################
# Guest Power Methods
################################################################################

    def start(self, vm):

        if vm.runtime.powerState == 'poweredOn':
            return False, dict(changed = False, msg = '%s is already powered on.' % vm.name)
        task = vm.PowerOn()
        worked, msg, _ = self._wait_task(task)
        return worked, dict(changed = True, msg = msg)

    def stop(self, vm):

        if vm.runtime.powerState == 'poweredOff':
            return False, dict(msg = '%s is already powered off.' % vm.name)

        task = vm.PowerOff()
        worked, msg, task = self._wait_task(task)
        if isinstance( task.info.error, vim.fault.InvalidPowerState ):
            return False, dict(msg = '%s is already powered off.' % vm.name)

        return worked, dict(changed = True, msg = msg)

    def shutdown(self, vm, force = False):

        if vm.runtime.powerState == 'poweredOff':
            return False, dict(changed = False, msg = '%s is already powered off.' % vm.name)

        if vm.guest.toolsRunningStatus != 'guestToolsRunning':
            if force:
                return self.stop(vm)
            else:
                return True, dict(msg='Cannot shutdown %s. Guest Tools are not currently running.')

        try:
            vm.ShutdownGuest()
        except vim.fault.InvalidPowerState:
            return False, dict(changed = False, msg = '%s is already powered off.' % vm.name)

        if self._wait_for_shutdown(vm):
            return False, dict(changed = True, msg = 'Successfully shutdown %s' % vm.name)
        else:
            if force:
                return self.stop(vm)
            return True, dict(msg = 'Failed to shutdown %s' % vm.name)

    def _wait_for_shutdown(self, vm):

        finish_time = time.time() + self.timeout
        while time.time() < finish_time:
            if vm.runtime.powerState == 'poweredOff':
                return True

        return False

################################################################################
# Guest Snapshot Methods
################################################################################

    def _find_snapshot_by_name(self, vm, name):
        def find_snap(tree, name):
            if tree.name == name:
                return tree
            else:
                for child in tree.childSnapshotList:
                    s = find_snap(child, name)
                    if s is not None:
                        return s

        snap = None
        try:
            for root_snap in vm.snapshot.rootSnapshotList:
                snap = find_snap(root_snap, name)
                if snap is not None:
                    break
        except (IndexError, AttributeError):
            snap = None

        return snap

    def create_snapshot(self, vm, name, description = '',
                        memory = False, quiesce = False):
        if name is None:
            return True, dict(msg = 'The snapshot name needs to be specified')
        if self._find_snapshot_by_name(vm, name) is not None:
            return False, dict(changed = False,
                msg = '%s already has a snapshot by the name %s' %(vm.name, name))

        task = vm.CreateSnapshot(name = name, description = description,
                                 memory = memory, quiesce = quiesce)

        failed, out, _ = self._wait_task(task)
        return failed, dict(changed = True, msg = out)

    def remove_snapshot(self, vm, name, remove_children = False):
        if name is None:
            return True, dict(msg = 'The snapshot name needs to be specified')
        snap = self._find_snapshot_by_name(vm, name)
        if snap is None:
            return False, dict(changed = False,
                msg = '%s does not have a snapshot by the name %s' %(vm.name, name))

        task = snap.snapshot.Remove(removeChildren = remove_children)
        failed, out, _ = self._wait_task(task)
        return failed, dict(changed = True, msg = out)

    def revert_snapshot(self, vm, name = None, suppress_power_on = False):

        if name is None:
            task = vm.RevertToCurrentSnapshot(suppressPowerOn = suppress_power_on)
        else:
            snap = self._find_snapshot_by_name(vm, name)
            if snap == None:
                self.module.fail_json(
                    msg = 'Snapshot named "%s" does not exist' %(name))
            task = snap.snapshot.Revert(suppressPowerOn = suppress_power_on)

        failed, out, _ = self._wait_task(task)
        return failed, dict(changed = True, msg = out)

################################################################################
# Folder Methods
################################################################################

    def create_folder(self, folder):

        failed = False
        parent = self.get_container_view([vim.Folder],
                folder.get('parent', 'Datacenters'),
                limit = {'type': 'Datacenter', 'name': self.datacenter.name })
        try:
            f = parent.CreateFolder(folder['name'])
        except vim.fault.DuplicateName as e:
            out = e.msg
            changed = False
        except vim.fault as e:
            failed = True
            out = e.msg
            changed = False
        else:
            changed = True
            out = 'Successfully created "%s.%s"' \
                  % ( parent.name, f.name )
        return failed, dict(changed = changed, msg = out)

    def destroy_folder(self, folder):

        f = self.get_container_view([vim.Folder], folder['name'])
        task = f.Destroy()
        failed, out, _ = self._wait_task(task)
        return failed, dict(changed = True, msg = out)

################################################################################
# VM Methods
################################################################################

    def run_task(self, vm, spec):
        task_name = spec['type']
        spec_value = spec.get('value', {})
        self.update_spec(spec_value)
        task = getattr(vm, task_name)(**spec_value)
        failed, out, _ = self._wait_task(task)
        return failed, dict(changed = True, msg = out)

    def upgrade_tools(self, vm):

        if vm.guest.toolsVersionStatus2 == 'guestToolsCurrent':
            return False, dict(changed = False, msg = 'Tools already current.')
        else:
            finish_time = time.time() + self.timeout
            while time.time() < finish_time:
                if vm.guest.toolsRunningStatus == 'guestToolsRunning':
                    return self.run_task(vm, {'type' : 'UpgradeTools_Task'})
                else:
                    continue
        return True, dict(msg = 'Guest tools need to be running to upgrade them.')

    def destroy_vm(self, vm):
        return self.run_task(vm, {'type' : 'Destroy'})

    def create_vm(self, guest, spec, devices = None ):
        spec_value = spec.get('value', {})
        self.update_spec(spec_value)

        vm_confspec = getattr(vim, spec.get('type'))(
                name = guest['name'], **spec_value)
        pool = guest.get('resource_pool', None)
        if pool is None:
            compute = self.get_container_view([vim.ComputeResource],
                self.module.params.get('compute_resource', None))
            if isinstance(compute, list):
                compute = compute[0]
            rp = compute.resourcePool
        else:
            rp = self.get_container_view([vim.ResourcePool], pool)


        try:
            folder = self.get_container_view([vim.Folder],
                    guest.get('folder', self.datacenter.vmFolder.name))
        except IndexError:
            self.module.fail_json(
                msg = 'Could not find the folder "%s"' % guest['folder'])

        task = folder.CreateVm(vm_confspec, rp)
        failed, out, _ = self._wait_task(task)
        return failed, dict(changed = True, msg = out)

    def clone_vm(self, guest, spec, devices = None ):
        spec_value = spec.get('value', {})
        self.update_spec(spec_value)
        vm_clonespec = getattr(vim, spec.get('type'))(**spec_value)

        parent = guest['clone_from']
        try:
            parent = self.get_container_view([vim.VirtualMachine],
                    guest.get('clone_from'))
        except IndexError:
            self.module.fail_json(
                msg = 'Could not fine the Virtual Machine to clone from, %'
                % guest['clone_from'] )

        try:
            folder = self.get_container_view([vim.Folder],
                    guest.get('folder', self.datacenter.vmFolder.name))
        except IndexError:
            self.module.fail_json(
                msg = 'Could not find the folder "%s"' % guest['folder'])

        task = parent.Clone(folder, guest['name'], vm_clonespec)
        failed, out, _ = self._wait_task(task)
        return failed, dict(changed = True, msg = out)

    def rename_vm(self, vm, new_name):
        if new_name is None:
            return True, dict(msg = 'The new vm name needs to be specified')
        task = vm.Rename(new_name)
        failed, out, _ = self._wait_task(task)
        return failed, dict(changed = True, msg = out)


################################################################################
# Guest Operations Methods
################################################################################

    def _run_guest_op_command(self, command, spec_value):
        fail = True
        finish_time = time.time() + self.timeout
        while time.time() < finish_time:
            try:
                out = command(**spec_value)
                fail = False
                break
            except vim.fault.GuestOperationsUnavailable as e:
                out = e.msg
                continue
            except vim.fault as e:
                self.module.fail_json(msg = e.msg)

        return fail, out

    def guest_operation(self, manager, spec):
        manager = getattr(self.content.guestOperationsManager, manager)

        try:
            command = getattr(manager, spec.get('type'))
        except AttributeError:
            self.module.fail_json(msg='Failed to find %s command for manager, %s.'
                                  %(spec.get('type', 'NOT GIVEN'), manager))
        spec_value = spec.get('value', {})
        self.update_spec(spec_value)

        fail, out = self._run_guest_op_command( command, spec_value)

        try:
            encodedOut = json.loads(
                { 'command' : spec.get('type'),
                  'out' : json.dumps(out, cls = VsphereJsonEncoder) } )
        except TypeError:
            encodedOut = str( out )

        return fail, dict(changed = True, guest_operation = encodedOut)

    def put_file_in_guest(self, local_path, spec):
        fm = self.content.guestOperationsManager.fileManager

        size = os.path.getsize(local_path)
        spec_value = spec.get('value', {})
        self.update_spec(spec_value)
        spec_value.update( { 'fileSize' : size } )

        command = fm.InitiateFileTransferToGuest
        fail, out = self._run_guest_op_command( command, spec_value)

        if fail:
            self.module.fail_json(msg = out)

        if re.search(r'http[s]://\*/', out):
            # Assume that the vsphere host we are connected to
            # is the host that vsphere is looking for.
            out = re.sub(r'/\*/', '/%s/' % self.vsphere_host, out)

        try:
            import requests
        except ImportError:
            self.module.fail_json(msg = 'Need requests package to put file on guest.')

        with open(local_path, 'r') as fd:
            res = requests.put(out, data = fd, verify=False)
            failed = False if res.status_code == 200 else True

        return failed, dict(
            changed = True,
            msg = 'Uploaded file to server. Status Code: %d, Text %s'
            %( res.status_code, res.text) )


    def get_file_in_guest(self, local_path, spec):
        fm = self.content.guestOperationsManager.fileManager

        spec_value = spec.get('value', {})
        self.update_spec(spec_value)

        command = fm.InitiateFileTransferFromGuest
        fail, out = self._run_guest_op_command( command, spec_value)

        if fail:
            self.module.fail_json(msg = out)

        url = out.url

        if re.search(r'http[s]://\*/', url):
            # Assume that the vsphere host we are connected to
            # is the host that vsphere is looking for.
            url = re.sub(r'/\*/', '/%s/' % self.vsphere_host, url)

        try:
            import requests
        except ImportError:
            self.module.fail_json(msg='Need requests package to put file on guest.')

        res = requests.get(url, stream = True, verify=False)
        if res.status_code == 200:
            with open(local_path, 'w') as fd:
                for chunk in res.iter_content(1024):
                    fd.write(chunk)
            failed = False
            msg = 'Successfully downloaded file from guest.'
        else:
            failed = True
            msg = 'Failed to download file from guest.'

        return failed, dict(changed = True, msg = msg)


def core(module):
    guest = module.params.get('guest', None)
    snapshot = module.params.get('snapshot', None)
    guest_operations_manager = module.params.get('guest_operations_manager', None)
    put_file = module.params.get('put_file', None)
    get_file = module.params.get('get_file', None)
    spec_param = module.params.get('spec', {})
    spec = copy.deepcopy(spec_param)

    folder = module.params.get('folder', dict())

    v = Vsphere(module)

    if folder is not None:
        folder_state = folder.get('state', None)
        if folder_state is not None:
            if folder_state == 'present':
                failed, res = v.create_folder(folder)
            elif folder_state == 'absent':
                failed, res = v.destroy_folder(folder)
            else:
                module.fail_json(
                    msg = 'Currently do not support state "%s" for folder'
                    % folder_state)
            return failed, res

    if guest is not None:
        try:
            vm = v.get_container_view([vim.VirtualMachine], guest['name'])
            exists = True
        except KeyError:
            module.fail_json(msg = 'Guest option requires the name field.')
        except IndexError:
            exists = False

    if snapshot:
        if guest is None:
            module.fail_json(msg='The guest option needs to be specified')
        if not exists:
            module.fail_json(msg='The vm %s does not exist.' % guest['name'])

        try:
            snapshot_action = snapshot['action']
        except KeyError:
            module.fail_json(msg='Need to specify an snapshot action to perform')

        name = snapshot.get('name', None)
        if snapshot_action == 'create':
            memory = snapshot.get('memory', False)
            quiesce = snapshot.get('quiesce', False)
            description = snapshot.get('description', '')
            failed, res = v.create_snapshot(vm, name, description = description,
                                            memory = memory, quiesce = quiesce)
        elif snapshot_action == 'remove':
            children = snapshot.get('children', False)
            failed, res = v.remove_snapshot(vm, name, children)

        elif snapshot_action == 'revert':
            suppress_power = snapshot.get('suppress_power', False)
            failed, res = v.revert_snapshot(vm, name, suppress_power)
        else:
            module.fail_json(msg = 'Currently do not support action "%s" for snapshot' % snapshot_action)

        return failed, res

    if guest_operations_manager:
        if put_file is not None:
            return v.put_file_in_guest(put_file, spec)
        elif get_file is not None:
            return v.get_file_in_guest(get_file, spec)
        else:
            return v.guest_operation(guest_operations_manager, spec)

    guest_state = guest.get('state', '')
    action = guest.get('action', None)
    if not exists:
        if guest_state == 'present':
            if guest.get( 'clone_from', None ) is not None:
                return v.clone_vm(guest, spec)
            else:
                return v.create_vm(guest, spec)
        elif guest_state == 'absent':
            failed = False
            res = dict(changed = False, msg = '%s is already absent' % guest['name'])
            return failed, res

        if action is not None:
            return True, dict(msg = 'VM needs to exist to perform action on it.')
    else:
        if action is not None:
            if action == 'upgrade_tools':
                return v.upgrade_tools(vm)
            elif action == 'task':
                return v.run_task(vm, spec)
            elif action == 'rename':
                new_name = guest.get('new_name', None)
                return v.rename_vm(vm, new_name)
        else:
            if guest_state == 'process':
                return v.start_process(guest, spec)
            elif guest_state == 'running':
                return v.start(vm)
            elif guest_state == 'stopped':
                return v.stop(vm)
            elif guest_state == 'shutdown':
                return v.shutdown(vm, guest.get('force', False))
            elif guest_state == 'absent':
                return v.destroy_vm(vm)
            elif guest_state == 'present':
                return False, dict(changed = False,
                                   msg = '%s already exists.' % guest['name'])

    return True, dict(msg = 'Unknown set of parameters were given.')

def main():
    module = AnsibleModule(
        argument_spec = dict(
            host = dict(required=True),
            login = dict(required=True),
            password = dict(required=True),
            checkssl=dict(required=False,default='true'),
            guest = dict(type='dict'),
            datacenter = dict(type = 'str'),
            folder = dict(type='dict'),
            snapshot = dict(type='dict'),
            guest_operations_manager = dict(),
            put_file = dict(),
            get_file = dict(),
            spec = dict(type = 'dict'),
            timeout = dict(type='int', default=60),
            compute_resource = dict(type='str')
        )
    )

    try:
        failed, result = core(module)
    except Exception as e:
        import traceback
        module.fail_json(msg = '%s: %s\n%s' %(e.__class__.__name__, str(e), traceback.format_exc()))

    if failed:
        module.fail_json(**result)
    else:
        module.exit_json(**result)

from ansible.module_utils.basic import *
main()
Contact GitHub API Training Shop Blog About
© 2016 GitHub, Inc. Terms Privacy Security Status Help
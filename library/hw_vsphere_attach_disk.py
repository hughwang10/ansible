#!/usr/bin/env python
DOCUMENTATION = '''
---
module: vsphere_attach_disk
author: MSP Cloud Platform
version_added: "0.0.1"
short_description: Load file to VMWare datastore
requirements: [ pyshpere, pyVmomi ]
description:
    - Load a file to vmware datastore
options:
    disk_file_path:
        required: true
        description:
            - Path and name to .vmdk file to mount.

    vcenter:
        required: true
        description:
            - Vsphere vcenter

    vcusername:
        required: true
        description:
            - Vsphere vcusername

    vcpassword:
        required: true
        description:
            - Vsphere vcpassword

    datacenter:
        required: true
        description:
            - Vsphere datacenter

    datastore:
        required: true
        description:
            - Vsphere datastore

    esxihostname:
        required: true
        description:
            - Vsphere esxi hostname

'''

import atexit
import time

from pyVmomi import vim, vmodl
from pyVim import connect
from pyVim.connect import Disconnect
import ssl

import time

def FindSCSIDisk(controller, unit, vm):
    for device in vm.config.hardware.device: 
       if isinstance(device, vim.vm.device.VirtualDisk):
         if (device.unitNumber == unit and (controller+1000) == device.controllerKey): 
           return device

def RemoveDevice(vm1, device, fileop = None):
   # Helper to do the removal of a single device.
   cspec = vim.vm.ConfigSpec()
   cspec = RemoveDeviceFromSpec(cspec, device)
   task = vm1.Reconfigure(cspec)
   wait_for_task(task)
   return vm1

def RemoveDeviceFromSpec(cspec, device, fileop = None):
   """ Remove the specified device from the vm """
   devSpec = vim.vm.device.VirtualDeviceSpec()
   devSpec.device = device
   devSpec.operation = vim.vm.device.VirtualDeviceSpec.Operation.remove

#   devSpec2 = vim.vm.device.VirtualDeviceSpec()
#   devSpec2.device = device
   devSpec.fileOperation = vim.vm.device.VirtualDeviceSpec.FileOperation.destroy 

#   if cspec.deviceChange == None:
#      cspec.deviceChange = []

   my_deviceChange = cspec.deviceChange
   my_deviceChange.append(devSpec) 
#   my_deviceChange.append(devSpec2) 

   #seems the err is here, but how to fix it ?
   cspec.deviceChange = my_deviceChange
   
   return cspec

def wait_for_task(task, actionName='job', hideResult=False):
    """
    Waits and provides updates on a vSphere task
    """

    while task.info.state == vim.TaskInfo.State.running:
        time.sleep(2)

    if task.info.state == vim.TaskInfo.State.success:
        if task.info.result is not None and not hideResult:
            out = '%s completed successfully, result: %s' % (actionName, task.info.result)
            print out
        else:
            out = '%s completed successfully.' % actionName
            print out
    else:
        out = '%s did not complete successfully: %s' % (actionName, task.info.error)
        raise task.info.error
        print out

    return task.info.result

def main():
    module = AnsibleModule(
        argument_spec = dict(
            disk_file_path=dict(required=True, type='str'),
            vm_name=dict(required=True, type='str'),
            vcenter=dict(required=True, type='str'),
            vcusername=dict(required=True, type='str'),
            vcpassword=dict(required=True, type='str'),
            datacenter=dict(required=True, type='str'),
            datastore=dict(required=True, type='str'),
            esxihostname=dict(required=True, type='str'),
            folder_name=dict(default="", type='str'),
        ),
        supports_check_mode=True
    )
    try:
        si = None
        context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
        context.verify_mode = ssl.CERT_NONE
        vsphere_vcenter = module.params.get('vcenter')
        vsphere_vcusername = module.params.get('vcusername')
        vsphere_vcpassword = module.params.get('vcpassword')
        vsphere_datacenter = module.params.get('datacenter')
        vsphere_datastore = module.params.get('datastore')
        vsphere_esxihostname = module.params.get('esxihostname')
        disk_path = module.params.get('disk_file_path')
        vm_name = module.params.get('vm_name')
        folder_name = module.params.get('folder_name')
        try:
            si = connect.SmartConnect(
                host=vsphere_vcenter,
                user=vsphere_vcusername,
                pwd=vsphere_vcpassword,
                port=443,
                sslContext=context)
        except IOError as e:
            pass
        if not si:
            print ">>> system exit!"
            raise SystemExit(-1)

        # Ensure that we cleanly disconnect in case our code dies
        atexit.register(connect.Disconnect, si)

        content = si.RetrieveContent()

        datacenter = module.params.get('datacenter', None)
        dc = [entity for entity in content.rootFolder.childEntity
                        if hasattr(entity, 'vmFolder') and entity.name == datacenter][0]


        search = content.searchIndex
        vm = search.FindByInventoryPath( vsphere_datacenter + '/vm/' + folder_name + '/' + vm_name )
        if vm == None:
          vm = search.FindByDatastorePath(dc, '[' + vsphere_datastore + '] ' + vm_name + '/' + vm_name + '.vmx')

        disk1 = FindSCSIDisk(0, 0, vm)
        RemoveDevice(vm, disk1)

        # the details we will need to make the disk:
        disk_path = '[' + vsphere_datastore + '] ' + disk_path
#        capacity = 16 * 1024 * 1024
        controller = None
        devices = vm.config.hardware.device
        for device in devices:
            if isinstance(device, vim.vm.device.VirtualSCSIController):
                controller = device

        virtual_disk = vim.vm.device.VirtualDisk()

        # https://github.com/vmware/pyvmomi/blob/master
        # /docs/vim/vm/device/VirtualDisk/FlatVer2BackingInfo.rst
        virtual_disk.backing = \
            vim.vm.device.VirtualDisk.FlatVer2BackingInfo()

        # https://github.com/vmware/pyvmomi/blob/master
        # /docs/vim/vm/device/VirtualDiskOption/
        # DiskMode.rst#independent_persistent
        virtual_disk.backing.diskMode = \
            vim.vm.device.VirtualDiskOption.DiskMode.persistent

        virtual_disk.backing.thinProvisioned = True
        virtual_disk.backing.eagerlyScrub = False
        virtual_disk.backing.fileName = disk_path

        virtual_disk.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
        virtual_disk.connectable.startConnected = True
        virtual_disk.connectable.allowGuestControl = False
        virtual_disk.connectable.connected = True

        virtual_disk.key = -100
        virtual_disk.controllerKey = controller.key
        virtual_disk.unitNumber = 0
#        virtual_disk.capacityInKB = capacity

        device_spec = vim.vm.device.VirtualDiskSpec()
        device_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
        device_spec.device = virtual_disk

        spec = vim.vm.ConfigSpec()
        spec.deviceChange = [device_spec]

        task = vm.ReconfigVM_Task(spec)
        wait_for_task(task, si)

    except vmodl.MethodFault, e:
        print "Caught vmodl fault: %s" % e.msg
        raise SystemExit(-1)
    except Exception, e:
        print "Caught exception: %s" % str(e)
        raise SystemExit(-1)
    rc = None
    out = ''
    err = ''
    result = {}
    result['disk_file_path'] = "OK"
    result['vm_name'] = "OK"


    module.exit_json(**result)

# import module snippets
from ansible.module_utils.basic import *

# Start program
if __name__ == "__main__":
    main()


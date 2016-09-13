#!/usr/bin/env python
# Copyright (C) 2015 by
# Ericsson AB
# S-164 83 Stockholm
# Sweden
# Tel: +46 10 719 00 00
#
# The program may be used and/or copied only with the written permission
# from Ericsson AB, or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the program
# has been supplied.
#
# All rights reserved.

DOCUMENTATION = '''
---
module: vsphere_expand_disks
author: MSP Cloud Platform
version_added: "0.0.1"
short_description: Load file to VMWare datastore
requirements: [ pyshpere, pyVmomi ]
description:
    - Load a file to vmware datastore
options:
    disk_id:
        required: true
        description:
            - List of scsi addresses where to mount.

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

import time, ssl

def FindSCSIDisk(controller, unit, vm):
    ret_device = None
    for device in vm.config.hardware.device: 
       if isinstance(device, vim.vm.device.VirtualDisk):
         if (device.unitNumber == unit and (controller+1000) == device.controllerKey): 
           ret_device = device
           break
    return ret_device

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
            disk_id=dict(required=True, type='str'),
            vm_name=dict(required=True, type='str'),
            vcenter=dict(required=True, type='str'),
            vcusername=dict(required=True, type='str'),
            vcpassword=dict(required=True, type='str'),
            datacenter=dict(required=True, type='str'),
            datastore=dict(required=True, type='str'),
            disk_size=dict(required=True, type='str'),
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
        vsphere_datacenter = module.params.get('datacenter', None)
        vsphere_datastore = module.params.get('datastore')
        vsphere_esxihostname = module.params.get('esxihostname')
        disk_id = module.params.get('disk_id')
        disk_size = module.params.get('disk_size')
        vm_name = module.params.get('vm_name')
        folder_name = module.params.get('folder_name')
        try:
            si = connect.SmartConnect(host=vsphere_vcenter,
                                                    user=vsphere_vcusername,
                                                    pwd=vsphere_vcpassword,
                                                    port=int(443),
                                                    sslContext=context)
        except IOError as e:
            pass
        if not si:
            raise SystemExit(-1)

        # Ensure that we cleanly disconnect in case our code dies
        atexit.register(connect.Disconnect, si)

        content = si.RetrieveContent()
        dc = [entity for entity in content.rootFolder.childEntity
                        if hasattr(entity, 'vmFolder') and entity.name == vsphere_datacenter][0]


        search = content.searchIndex
        vm = search.FindByInventoryPath( vsphere_datacenter + '/vm/' + folder_name + '/' + vm_name )

        if vm == None:
          vm = search.FindByDatastorePath(dc, '[' + vsphere_datastore + '] ' + vm_name + '/' + vm_name + '.vmx')

        controller = None
        devices = vm.config.hardware.device
        for device in devices:
            if isinstance(device, vim.vm.device.VirtualSCSIController):
                controller = device
        
        virtual_disk = FindSCSIDisk(0, int(disk_id), vm)
        if virtual_disk != None:
          if 1024 * 1024 * int(disk_size) > virtual_disk.capacityInKB:

            disk_spec = vim.vm.device.VirtualDeviceSpec()
            disk_spec.device = vim.vm.device.VirtualDisk()
            disk_spec.device.key = virtual_disk.key
            disk_spec.device.backing = virtual_disk.backing
            disk_spec.device.backing.fileName = virtual_disk.backing.fileName
            disk_spec.device.backing.diskMode = virtual_disk.backing.diskMode
            disk_spec.device.controllerKey = virtual_disk.controllerKey
            disk_spec.device.unitNumber = virtual_disk.unitNumber
            disk_spec.device.capacityInKB = 1024 * 1024 * (int(disk_size))

            disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit

            vmconf = vim.vm.ConfigSpec()

            vmconf.deviceChange.append(disk_spec)

            task = vm.ReconfigVM_Task(vmconf)
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
    result['disk_id'] = "OK"
    result['vm_name'] = "OK"


    module.exit_json(**result)

# import module snippets
from ansible.module_utils.basic import *

# Start program
if __name__ == "__main__":
    main()


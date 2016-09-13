#!/usr/bin/env python

DOCUMENTATION = '''
---
module: vsphere_loadfile
author: MSP Cloud Platform
version_added: "0.0.1"
short_description: Load file to VMWare datastore
requirements: [ pyshpere, pyVmomi  ]
description:
    - Load a file to vmware datastore
options:
    iso_path:
        required: true
        description:
            - Path and name to .iso file to mount.

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
import time, ssl

from pyVmomi import vim, vmodl
from pyVim import connect
from pyVim.connect import Disconnect

def get_obj(content, vimtype, name):
    """
     Get the vsphere object associated with a given text name
    """
    obj = None
    container = content.viewManager.CreateContainerView(content.rootFolder, vimtype, True)
    for c in container.view:
        if c.name == name:
            obj = c
            break
    return obj


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
            iso_path=dict(required=True, type='str'),
            unit_number=dict(required=True, type='int'),            
            vm_name=dict(required=True, type='str'),
            vcenter=dict(required=True, type='str'),
            vcusername=dict(required=True, type='str'),
            vcpassword=dict(required=True, type='str'),
            datacenter=dict(required=True, type='str'),
            datastore=dict(required=True, type='str'),
            esxihostname=dict(required=True, type='str'),
        ),
        supports_check_mode=True
    )
    try:
        si = None
        context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
        context.verify_mode = ssl.CERT_NONE        
        vsphere_vcenter = module.params.get('vcenter')
        vsphere_vcusername = module.params.get('vcusername').replace("##at##","@")
        vsphere_vcpassword = module.params.get('vcpassword')
        vsphere_datacenter = module.params.get('datacenter')
        vsphere_datastore = module.params.get('datastore')
        vsphere_esxihostname = module.params.get('esxihostname')
        iso_path = module.params.get('iso_path')
        unit_number = module.params.get('unit_number')        
        vm_name = module.params.get('vm_name')
        try:
            si = connect.SmartConnect(host=vsphere_vcenter,
                                                    user=vsphere_vcusername,
                                                    pwd=vsphere_vcpassword,
                                                    port=int(443),
                                                    sslContext=context)
        except IOError as e:
            pass
        if not si:
            print("Could not connect to the specified host using specified "
                  "username and password")
            raise SystemExit(-1)

        # Ensure that we cleanly disconnect in case our code dies
        atexit.register(connect.Disconnect, si)

        content = si.RetrieveContent()

        vm = get_obj(content, [vim.VirtualMachine], vm_name)

        cdspec = None
        for device in vm.config.hardware.device:
            if isinstance(device, vim.vm.device.VirtualCdrom):
                if device.unitNumber == unit_number: 
                    cdspec = vim.vm.device.VirtualDeviceSpec()
                    cdspec.device = device
                    cdspec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit

                    cdspec.device.backing = vim.vm.device.VirtualCdrom.IsoBackingInfo()
                    for datastore in vm.datastore:
                        cdspec.device.backing.datastore =  datastore
                        break
                    cdspec.device.backing.fileName = '[' + vsphere_datastore + '] ' + iso_path
                    cdspec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
                    cdspec.device.connectable.startConnected = True
                    cdspec.device.connectable.allowGuestControl = True

        vmconf = vim.vm.ConfigSpec()
        vmconf.deviceChange = [cdspec]
        task = vm.ReconfigVM_Task(vmconf)

        wait_for_task(task, si)   

    except vmodl.MethodFault, e:
        raise SystemExit(-1)
    except Exception, e:
        raise SystemExit(-1)

    rc = None
    out = ''
    err = ''
    result = {}
    result['iso_path'] = "OK"
    result['vm_name'] = "OK"


    module.exit_json(**result)

# import module snippets
from ansible.module_utils.basic import *

# Start program
if __name__ == "__main__":
    main()


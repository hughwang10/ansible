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



try:
    import json
except ImportError:
    import simplejson as json


def main():
    module = AnsibleModule(
        argument_spec=dict(
            vcenter_hostname=dict(required=True, type='str'),
            username=dict(required=True, type='str'),
            password=dict(required=True, type='str'),
            vm_name=dict(required=True, type='str'),
            action=dict(required=True, type='str',
                        choices=['mount_vmtools', 'umount_vmtools','upgrade_tools']),
            group=dict(required=False, default=False, type='bool'),
            vm_folder=dict(required=False, default=None, type='str'),
            domain=dict(required=False, default=None, type='str'),
            datacenter_name=dict(required=False, default=None, type='str'),
            cluster_name=dict(required=False, default=None, type='str'),
            datastore=dict(required=False, default=None, type='str'),
        ),
        supports_check_mode=False
    )

    vcenter_hostname = module.params['vcenter_hostname']
    username = module.params['username']
    password = module.params['password']
    action = module.params['action']
    vm_name = module.params['vm_name']     
    group = module.params['group']
    domain = module.params['domain']
    datacenter_name = module.params['datacenter_name']
    cluster_name = module.params['cluster_name']
    datastore = module.params['datastore']
    #context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    #context.verify_mode = ssl.CERT_NONE
    # sslContext=context
    si = SmartConnect(
        host=vcenter_hostname,
        user=username,
        pwd=password,
        port=int(443))

    content = si.RetrieveContent()

    if action == 'upgrade_tools':
        vm = find_vm(module, vm_name, si)
        mount_tools(module, vm)
    else:
        module.fail_json(msg='%s is not a supported action' % action)

    atexit.register(Disconnect, si)


def find_vm(module, vm_name, si):
    content = si.RetrieveContent()
    vm = get_obj(content, [vim.VirtualMachine], vm_name)

    if not vm:
        module.fail_json(msg='vm %s does not exist' % vm_name)

    return vm

def get_obj(content, vimtype, name, **kwargs):
    obj = None
    obj_container = kwargs.get('container', content.rootFolder)
    container = content.viewManager.CreateContainerView(
        obj_container, vimtype, True)
    for c in container.view:
        if c.name == name:
            obj = c
            break
    return obj

def mount_tools(module, vm):
    changes = []
    changed = False
    if vm.guest.toolsVersionStatus2 == 'guestToolsNotInstalled':
        if not vm.summary.runtime.toolsInstallerMounted:
            vm.MountToolsInstaller()
            changes.append('vmtools mounted')
            changed = True  
        else:
            vm.UnmountToolsInstaller()
            changed = False
            changes.append('vmtools unmounted')            
    if changed:
        module.exit_json(changed=True, changes=changes)
    else:
        module.exit_json(changed=False, changes=changes)



from ansible.module_utils.basic import *
main()

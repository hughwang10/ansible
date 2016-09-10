'''
Hugh
'''

import atexit

from pyVmomi import vim, vmodl
from pyVim import connect
from pyVim.connect import Disconnect
import ssl

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


def create_vswitch(host_network_system, vss_name, num_ports, nic_name=None):
    vss_spec = vim.host.VirtualSwitch.Specification()
    vss_spec.numPorts = 120 #num_ports
    #vss_spec.bridge = vim.host.VirtualSwitch.SimpleBridge(nicDevice='pnic_key')
    if nic_name != None:
        vss_spec.bridge = vim.host.VirtualSwitch.BondBridge(nicDevice=[nic_name])    
    host_network_system.AddVirtualSwitch(vswitchName=vss_name, spec=vss_spec)

    print "Successfully created vSwitch ",  vss_name

def delete_vswitch(host_network_system, vss_name):
    #vss_spec = vim.host.VirtualSwitch.Specification()
    host_network_system.RemoveVirtualSwitch(vswitchName=vss_name)

    print "Successfully deleted vSwitch ",  vss_name    


def create_port_group(host_network_system, pg_name, vss_name):
    port_group_spec = vim.host.PortGroup.Specification()
    port_group_spec.name = pg_name
    port_group_spec.vlanId = 0
    port_group_spec.vswitchName = vss_name

    security_policy = vim.host.NetworkPolicy.SecurityPolicy()
    security_policy.allowPromiscuous = True
    security_policy.forgedTransmits = True
    security_policy.macChanges = False

    port_group_spec.policy = vim.host.NetworkPolicy(security=security_policy)

    host_network_system.AddPortGroup(portgrp=port_group_spec)

    print "Successfully created PortGroup ",  pg_name

def main():
    module = AnsibleModule(
        argument_spec = dict(         
            vcenter=dict(required=True, type='str'),
            vcusername=dict(required=True, type='str'),
            vcpassword=dict(required=True, type='str'),
            esxihostname=dict(required=True, type='str'),
        ),
        supports_check_mode=True
    )
    try:
        si = None
        vsphere_vcenter = module.params.get('vcenter')
        vsphere_vcusername = module.params.get('vcusername')
        vsphere_vcpassword = module.params.get('vcpassword')
        vsphere_esxihostname = module.params.get('esxihostname')
        try:
            si = connect.SmartConnect(host=vsphere_vcenter, user=vsphere_vcusername, pwd=vsphere_vcpassword, port=443)
        except IOError as e:
            pass
        if not si:
            print("Could not connect to the specified host using specified "
                  "username and password")
            raise SystemExit(-1)

        # Ensure that we cleanly disconnect in case our code dies
        atexit.register(connect.Disconnect, si)
        content = si.RetrieveContent()
        host = get_obj(content, [vim.HostSystem], vsphere_esxihostname)

        host_network_system = host.configManager.networkSystem
        #for item in dir(host_network_system):
        #    print item
        print "Done"

#         for pnic in host.config.network.pnic:
#             if pnic.device == inputs['nic_name']:
#                 pnic_key = pnic.key

        #create_vswitch(host_network_system, inputs['switch_name'], inputs['num_ports'])
        #create_vswitch(host_network_system, inputs['switch_name'], inputs['num_ports'], inputs['nic_name'])
        #create_port_group(host_network_system, inputs['port_group_name'], inputs['switch_name'])
        #delete_vswitch(host_network_system, inputs['switch_name'])

        #add_virtual_nic(host_network_system, inputs['port_group_name'])

    except vmodl.MethodFault, e:
        module.fail_json(msg=str(e.msg))
    except Exception, e:
        module.fail_json(msg=str(e))

    rc = None
    out = ''
    err = ''
    result = {}
    result['host_network'] = dir(host_network_system)


    module.exit_json(**result)        
# Start program
# this is magic, see lib/ansible/module_common.py
from ansible.module_utils.basic import *
if __name__ == "__main__":
    main()
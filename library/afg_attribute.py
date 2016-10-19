#!/usr/bin/python
import subprocess,time

def afg_get(afg_attribute,command,module):
    proc = subprocess.Popen([command + " get " +  afg_attribute], stdout=subprocess.PIPE, shell=True)
    output = proc.communicate()[0]
    if proc.returncode != 0:
        module.fail_json(msg='command get failed!')
    return output.strip()

def afg_set(afg_attribute,afg_attribute_value,command,module):
    proc = subprocess.Popen([command + " set " + afg_attribute + " " + afg_attribute_value], stdout=subprocess.PIPE, shell=True)
    proc.communicate()
    if proc.returncode != 0:
        module.fail_json(msg='command set failed with ' + str(proc.returncode))

def main():
    module = AnsibleModule(
        argument_spec=dict(
            attribute=dict(required=True, type='str'),
            attribute_cluster=dict(required=True, type='str'),            
            attribute_value=dict(required=True, type='str'),    
            attribute_confirm=dict(required=False, default=False, type='bool')                    
        )
    )

    afg_attribute = module.params['attribute']
    afg_attribute_value = module.params['attribute_value']
    afg_attribute_confirm = module.params['attribute_confirm']
    command = "/opt/miep/tools/msa/msaconfigctrl.sh -g " + module.params['attribute_cluster']
    output = afg_get(afg_attribute,command,module)

    changes = []
    changes.append(afg_attribute)
    changes.append(afg_attribute_value)    
    changes.append(afg_attribute_confirm)
    changes.append(output)      
    
    if (output !=  afg_attribute_value) and (afg_attribute_confirm == True):
        afg_set(afg_attribute,afg_attribute_value,command,module)
        module.exit_json(changed=True, changes=changes)
    elif output !=  afg_attribute_value:
        module.fail_json(msg="Audit failed: %s " % str(changes))
    else:
        module.exit_json(changed=False, changes=changes)    

from ansible.module_utils.basic import *
main()

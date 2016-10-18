#!/usr/bin/python
import subprocess

def afg_get(afg_attribute):
    proc = subprocess.Popen(["./demo.sh get"], stdout=subprocess.PIPE, shell=True)
    output = proc.communicate()[0]
    if proc.returncode != 0:
        module.fail_json(msg='command get failed!')
    return output.strip()

def afg_set(afg_attribute_value):
    proc = subprocess.Popen(["./demo.sh set " + afg_attribute_value], stdout=subprocess.PIPE, shell=True)
    proc.communicate()
    if proc.returncode != 0:
        module.fail_json(msg='command set failed!')

def main():
    module = AnsibleModule(
        argument_spec=dict(
            attribute=dict(required=True, type='str'),
            attribute_value=dict(required=True, type='str'),            
        )
    )


    afg_attribute = module.params['attribute']
    afg_attribute_value = module.params['attribute_value']
    changes = []
    changes.append(afg_attribute)
    changes.append(afg_attribute_value)
    
    if afg_get(afg_attribute) !=  afg_attribute_value:
        afg_set(afg_attribute_value)
        module.exit_json(changed=True, changes=changes)
    else:            
        module.exit_json(changed=False, changes=changes)    


from ansible.module_utils.basic import *
main()

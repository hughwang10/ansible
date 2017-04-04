#!/usr/bin/python
def main():
    module = AnsibleModule(
        argument_spec=dict(
            file_name = dict(required=True, type='str')               
        )
    )

    file_name = module.params['file_name']

    with open(file_name,'r') as f:
        data = f.readlines()
        
    with open(file_name,'w') as f:
        for line in data:
            line = line.replace('<TAG_',"{{")
            line = line.replace('_TAG>',"}}")        
            f.write(line)        

    changes = ['TAG replaced.']            
    module.exit_json(changed=True, changes=changes)
 

from ansible.module_utils.basic import *
main()

#!/usr/bin/python
import re, glob, yaml
from os.path import basename, dirname

def get_tags(file_name):
    result = []    
    with open(file_name) as f:
        content = f.readlines()

    for line in content:
        line = line.strip()
        if "<TAG_" in line and not line.startswith('#'):
            match = re.findall('<TAG_(.+?)_TAG>',line)
            if match:
                for item in match:
                    result.append(item)
    return result                

def replace_tags(file_name,config):    
    with open(file_name) as f:
        content = f.readlines()
    with open(dirname(file_name) + '/out_' + basename(file_name), 'w') as out_file:
        for line in content:
            if "<TAG_" in line and not line.strip().startswith('#'):
                match = re.findall('<TAG_(.+?)_TAG>',line)
                if match:
                    for item in match:
                        line = line.replace('<TAG_'+ item + '_TAG>', str(config[item]))
                    print line.strip() 
            out_file.write(line)   

def main():
    module = AnsibleModule(
        argument_spec=dict(
            site_config_dir =dict(required=True, type='str'),
            config_file_dir =dict(required=True, type='str'),
            site_name =dict(required=True, type='str'),
            gen_out_files =dict(required=False, default=False, type='bool')                   
        )
    )

    site_config_dir = module.params['site_config_dir']
    config_file_dir = module.params['config_file_dir'] 
    site_name = module.params['site_name']
    gen_out_files = module.params['gen_out_files']

    site_var = site_config_dir + "/vars"
    site_spec = site_config_dir + "/site_spec"    

    config_file =  config_file_dir + '/group_vars/all/' + site_name + '_config.yml'  
    
    result = []
    for name in glob.glob(site_var + '/' + site_name + '*'): 
        result += get_tags(name)
    for name in glob.glob(site_spec + '/' + site_name + '*'):    
        result += get_tags(name)  

    changes = []
    if not gen_out_files:
        config = {}
        for item in result:
            config[item] = 'N/A'
        site_outfile = config_file_dir+ '/' + site_name + '_config_prep.yml'    
        with open(site_outfile, 'w') as outfile:
            yaml.dump(config, outfile, default_flow_style=False)
        changes.append(site_outfile)    
    else:  
        with open(config_file, 'r') as stream:
            try:
                config = yaml.load(stream)
            except yaml.YAMLError as exc:
                module.fail_json(msg='failed to load configure: ' + str(exc))

        for name in glob.glob(site_var + '/' + site_name + '*'):
            replace_tags(name, config)
            changes.append(basename(name))
        for name in glob.glob(site_spec + '/' + site_name + '*'):     
            replace_tags(name, config) 
            changes.append(basename(name))             

    module.exit_json(changed=True, changes=changes)
 

from ansible.module_utils.basic import *
main()

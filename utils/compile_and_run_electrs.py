#%%
import requests, os, json
import tarfile


def install_dep():
    os.system('sudo apt install cargo  clang cmake build-essential ')


def download_electrs():    
    url = 'https://github.com/romanz/electrs/archive/refs/tags/v0.9.9.tar.gz'
    filename = 'electrs.tar.gz'
    
    if not os.path.exists(filename):    
        response = requests.get(url, stream = True)
        with open(filename, 'wb') as file:                
            for chunk in response.iter_content(chunk_size = 1024):
                if chunk:
                    file.write(chunk)
    
    return filename
    


def extract(filename):
    with tarfile.open(filename) as tar: 
        tar.extractall()
        return list(tar.getmembers())[0].name




def compile(electrs_folder):
    org_folder = os.path.abspath('.')
    os.chdir(electrs_folder)
    os.system('cargo build --locked --release')
    os.chdir(org_folder)


def specter_node_config(node_config_file='~/.specter_dev/nodes/default.json'):    
    import json
    node_config_file = os.path.expanduser(node_config_file)
    with open(node_config_file, "r") as file:
        node_config = json.load(file)
    
    return node_config


def create_config(node_config):       
    network = "regtest"
    electrs_config = f"""
        # File where bitcoind stores the cookie, usually file .cookie in its datadir
        cookie_file = "{node_config['datadir']}/{network if network!= 'mainnet' else ''}/.cookie"

        # The listening RPC address of bitcoind, port is usually 8332
        daemon_rpc_addr = "{node_config['host']}:{int(node_config['port'])}"

        # The listening P2P address of bitcoind, port is usually 8333
        daemon_p2p_addr = "{node_config['host']}:{int(node_config['port'])+1}"

        # Directory where the index should be stored. It should have at least 70GB of free space.
        db_dir = "./db"

        # bitcoin means mainnet. Don't set to anything else unless you're a developer.
        network = "{network}"

        # The address on which electrs should listen. Warning: 0.0.0.0 is probably a bad idea!
        # Tunneling is the recommended way to access electrs remotely.
        electrum_rpc_addr = "127.0.0.1:50000"

        # How much information about internal workings should electrs print. Increase before reporting a bug.
        log_filters = "INFO"    
    """
    with open('electrs.toml', "w") as file:
        file.write(electrs_config)




def run_electrs(electrs_folder, node_config):
    network = "regtest"
    cmd = f"{electrs_folder}/target/release/electrs --log-filters=INFO --db-dir ./db --daemon-dir  {node_config['datadir']}/{network if network!= 'mainnet' else ''}  --network {network}"
    os.system(cmd)




# %%
filename = download_electrs()
# %%
electrs_folder = extract(filename)
# %%
compile(electrs_folder)
# %%
node_config = specter_node_config()
# %%

create_config(node_config)    
# %%
run_electrs(electrs_folder, node_config)



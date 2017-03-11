'''Run with flask as an HTTP server to communicate starting points of CloudK-SVD and Consensus
'''
import json
import logging
import sys
import traceback
from configparser import ConfigParser
from multiprocessing import Process, Value
from urllib.parse import urlparse
import numpy as np
import adac.consensus.iterative as consensus
import adac.nettools as nettools
from adac.communicator import Communicator
import requests
from flask import Flask, request

APP = Flask(__name__)
TASK_RUNNING = Value('i', 0, lock=True)  # 0 == False, 1 == True
CONF_FILE = 'params.conf'


def data_loader(filename):
    '''Reads in data line by line from file. and stores in Numpy array

    Each line of the file is a new vector with the format 1, 2, 3, ..., n where
     n is the length of the vector

    Args:
        str: name of data file

    Returns:
        Numpy array: vectors read from each line of file

    '''

    vectors = []
    with open(filename, 'r') as f:
        for line in f:
            v = list(map(lambda x: int(x), line.split(' ')))
            vectors.append(v)
        data = np.array(vectors)

    return data


def get_neighbors():
    '''Gets IP addresses of neigbors for given node

    Args:
            N/A

    Returns:
            (iterable): list of IP addresses of neighbors
    '''

    global CONF_FILE
    con = ConfigParser()
    con.read(CONF_FILE)
    v = json.loads(con['graph']['nodes'])
    e = json.loads(con['graph']['edges'])
    ip = nettools.get_ip_address('wlan0')
    i = v.index(ip)
    n = []
    for x in range(len(v)):
        if e[i][x] == 1 and x != i:
            n.append(v[x])

    return n


@APP.route("/start/consensus")
def run():
    '''Start running distributed consensus on a
    separate process.

    The server will not kick off a new consensus
     job unless the current consensus has already completed.

    Args:
        N/A

    Returns:
        str: A message detailing whether or not the consensus
         job was started.
    '''
    msg = ""
    global TASK_RUNNING
    logging.debug('Attempting to kickoff task')
    if TASK_RUNNING.value != 1:
        iterations = 50
        try:
            iterations = int(request.args.get('tc'))
        except:
            iterations = 50
        logging.debug('Setting consensus iterations to {}'.format(iterations))
        p = Process(target=kickoff, args=(TASK_RUNNING,iterations,))
        p.daemon = True
        p.start()
        logging.debug('Started new process')
        msg = "Started Running Consensus"
        with TASK_RUNNING.get_lock():
            TASK_RUNNING.value = 1
    else:
        logging.debug('Task already running')
        msg = "Consensus Already Running. Please check logs"

    return msg


@APP.route("/start/cloudksvd")
def run2():
    '''Placeholder for when we want to start running Cloud K-SVD using this paradigm.
    '''
    global TASK_RUNNING
    return "We can't run Cloud K-SVD quite yet. Please check back later."


def kickoff(task, tc):
    '''The worker method for running distributed consensus.

        Args:
            task (int): The process-shared value denoting whether the taks is running or not.

        Returns
            N/A
    '''
    # This the where we would need to do some node discovery, or use a pre-built graph
    # in order to notify all nodes they should begin running
    global CONF_FILE
    config = ConfigParser()
    logging.debug('Task was kicked off.')

    config.read(CONF_FILE)
    port = config['consensus']['udp_port']
    logging.debug('Communicating on port {}'.format(port))
    c = Communicator('udp', int(port))
    c.listen()
    logging.debug('Now listening on new UDP port')
    ####### Notify Other Nodes to Start #######
    port = config['node_runner']['port']
    logging.debug('Attempting to tell all other nodes in my vicinity to start')
    neighs = get_neighbors()
    for node in neighs:
        req_url = 'http://{}:{}/start/consensus?tc={}'.format(node, port, tc)
        logging.debug('Kickoff URL for node {} is {}'.format(node, req_url))
        try:
            requests.get(req_url)
        except:
            logging.debug("Could not hit node {} at {}".format(node, req_url))
    ########### Run Consensus Here ############
    # Load parameters:
    # Load original data
    # get neighbors and weights get_weights()
    # Pick a tag ID (doesn't matter) --> 1
    # communicator already created
    logging.debug('Got neighbors {}'.format(neighs))
    weights = consensus.get_weights(neighs)
    logging.debug('got weights {}'.format(weights))
    data = data_loader(config['data']['file'])
    logging.debug('Loaded data')
    try:
        consensus_data = consensus.run(data, tc, 1, weights, c)
        logging.info("~~~~~~~~~~~~~~CONSENSUS DATA BELOW~~~~~~~~~~~~~~~~")
        logging.info('{}'.format(consensus_data))
        logging.info("~~~~~~~~~~~~~~CONSENSUS DATA ABOVE~~~~~~~~~~~~~~~~")
        logging.debug('Ran consensus')
        # Log consensus data here
        ###########################################
    except:
        logging.error('Consensus threw an exception.')
        exc_type, exc_value, exc_traceback = sys.exc_info()
        # logging.error("Error: {}".format(e))
        logging.error(repr(traceback.format_tb(exc_traceback)))
    c.close()
    with task.get_lock():
        task.value = 0


@APP.route('/degree')
def get_degree():
    '''Get the degree of connections for this node.

    We assume the node is always connected to itself, so the number should always be atleast 1.
    '''
    global CONF_FILE
    c = ConfigParser()
    c.read(CONF_FILE)
    # req_url = urlparse(request.url)
    # host = o.hostname
    host = request.args.get('host')
    a = json.loads(c['graph']['nodes'])
    e = json.loads(c['graph']['edges'])
    host_index = a.index(host)
    cnt = 0
    for j in e[host_index]:
        cnt += j

    cnt -= 1
    # minus one to exlude no self-loops from count
    return str(cnt)


def start():
    # Use a different config other than the default if user specifies
    global config_file
    config = ConfigParser()
    if len(sys.argv) > 1:
        CONF_FILE = sys.argv[1]
    else:
        CONF_FILE = "params.conf"
    config.read(CONF_FILE)


    root_level = int(config['logging']['level'])
    logging.basicConfig(filename=config['logging']['log_file'], level=root_level)
    root = logging.getLogger()
    root.setLevel(root_level)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(root_level)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    root.addHandler(ch)

    nr = config['node_runner']
    APP.run(nr['host'], nr['port'])

if __name__ == "__main__":
    start()
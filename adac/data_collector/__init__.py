'''Upload data from experiments where the logs can be viewed and stored
'''
import json
from flask import Flask, request
from peewee import SqliteDatabase

def set_db(db_name):
    '''Set the app database'''
    return SqliteDatabase(db_name)

APP = Flask(__name__)
DB = set_db(__name__)

from adac.data_collector.models import Statistic, Event


@APP.route('/logs/<node>', methods=['GET', 'POST'])
def logs(node):
    '''Upload or download the run logs '''
    print("Node: {}".format(node))
    if request.method is 'GET':
        results = Event.select().where(Event.node_name == node)
        return json.dumps(results)
    elif request.method is 'POST':
        data = request.get_json()
        for d in data:
            Event.create(node_name=d['node_name'],
                         timestamp=d['timestamp'],
                         event_name=d['event_name'],
                         event_data=d['event_data'])
        return json.dumps({'msg': "Success"})


@APP.route('/statistics/<node>', methods=['GET', 'POST'])
def statistics(node):
    '''Upload or download statistics froma specific node
    Args:
        node (str): The name of the node
    '''
    if request.method is 'GET':
        results = Statistic.select().where(Statistic.node_name == node)
        return json.dumps(results)
    elif request.method is 'POST':
        data = request.get_json()
        for d in data:
            Statistic.create(node_name=d['node_name'],
                             timestamp=d['timestamp'],
                             statistic_type=d['statistic_type'],
                             statistic_value=d['statistic_value'])
        return json.dumps({'msg': "Success"})



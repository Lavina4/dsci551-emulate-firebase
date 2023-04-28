"""
python: 3.11.0
flask: 2.2.3
flask_socketio: 5.3.3
pymongo: 4.3.3
"""

from flask import Flask, jsonify, request
from pymongo import MongoClient
from collections import OrderedDict
import numbers, json
from itertools import islice
from flask_socketio import SocketIO
import uuid


app = Flask(__name__)
socketio = SocketIO(app)
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

def check_index(key):
    key = key.strip('"\'')
    indexes = db.jobs.index_information()
    flag = False
    for index in indexes:
        index_key = indexes[index]['key'][0][0]
        if key == index_key:
            flag = True
            break
    if not flag:
        db.jobs.create_index(key)

def create_projection(path):
    return {path: 1}

def get_response(res_dict, paths):
    for path in paths[1:]:
        res_dict = res_dict[path]
    return res_dict


## Sorting the groupBy data
def sort_order(response):
    nulls = {}
    bools_true = {}
    bools_false = {}
    numeric = {}
    string = {}
    objects = {}

    for k in response:
        if response[k] == None:
            nulls[k] = response[k]
        elif response[k] == True:
            bools_true[k] = response[k]
        elif response[k] == False:
            bools_false[k] = response[k]
        elif isinstance(response[k], numbers.Number):
            numeric[k] = response[k]
        elif isinstance(response[k], str):
            string[k] = response[k]
        else:
            objects[k] = response[k]
    nulls = OrderedDict(sorted(nulls.items()))
    bools_true = OrderedDict(sorted(bools_true.items()))
    bools_false = OrderedDict(sorted(bools_false.items()))
    numeric = OrderedDict(sorted(numeric.items(), key=lambda d: (d[1], d[0])))
    string = OrderedDict(sorted(string.items(), key=lambda d: (d[1], d[0])))
    objects = OrderedDict(json.loads(json.dumps(objects, sort_keys=True)))
    final = OrderedDict()
    for n in nulls:
        final[n] = nulls[n]
    for bf in bools_false:
        final[bf] = bools_false[bf]
    for bt in bools_true:
        final[bt] = bools_true[bt]
    for num in numeric:
        final[num] = numeric[num]
    for s in string:
        final[s] = string[s]
    for o in objects:
        final[o] = objects[o]
    return final

## ordering the data on $key / $value / child
def get_orderBy(orderBy, response, key):
    app.json.sort_keys = False
    if orderBy == '"$key"' or orderBy == "'$key'":
        temp_dict = list(response)
        objects = []
        for t in temp_dict:
            objects.append(OrderedDict(json.loads(json.dumps(t, sort_keys=True))))
        return objects, temp_dict
    elif orderBy == '"$value"' or orderBy == "'$value'":
        if key:
            check_index(key)
        temp_res = list(response)
        if len(temp_res) > 1:
            return None, temp_res
        res = temp_res[0]
        if '_id' in res:
            res = {i: res[i] for i in res if i != '_id'}
        path = list(res.keys())[0] if len(res.keys()) == 1 else None
        if path:
            if isinstance(res[path], dict) or isinstance(res[path], OrderedDict):
                response = sort_order(res[path])
            else:
                response = res
        elif isinstance(res, dict) or isinstance(res, OrderedDict):
            response = sort_order(res)
        else:
            response = res
        if isinstance(response, OrderedDict):
            response = OrderedDict([(path,response)]) if path else response
        else:
            response = OrderedDict([(path,response[path])]) if path else response
        return [response], [res]
    else: ## order by child
        order_by = orderBy.split('/')
        check_index(order_by[-1])
        order_by = '.'.join(order_by)
        res = response.sort(order_by.strip('"'))
        return list(res), response

## startAt and endAt for $key
def startAt_endAt_key(startAt, endAt, r, key, dict_record):
    if not key: ## /.json case
        if startAt and endAt:
            if not isinstance(startAt, int) and not isinstance(endAt, int):
                if startAt.isnumeric() and endAt.isnumeric():
                    if int(r['_id']) >= int(startAt) and int(r['_id']) <= int(endAt): dict_record[r['_id']] = r
            else:
                if r['_id'] >= startAt and r['_id'] <= endAt: dict_record[r['_id']] = r
        elif startAt:
            if not isinstance(startAt, int):
                if startAt.isnumeric():
                    if int(r['_id']) >= int(startAt): dict_record[r['_id']] = r
            else:
                if r['_id'] >= startAt: dict_record[r['_id']] = r
        else:
            if not isinstance(endAt, int):
                if endAt.isnumeric():
                    if int(r['_id']) <= int(endAt): dict_record[r['_id']] = r
            else:
                if r['_id'] <= endAt: dict_record[r['_id']] = r
    else:
        for d in r:
            if startAt and endAt:
                if d >= startAt and d <= endAt: dict_record[d] = r[d]
            elif startAt:
                if d >= startAt: dict_record[d] = r[d]
            else:
                if d <= endAt: dict_record[d] = r[d]
    return dict_record

## startAt and endAt filtering
def startAt_endAt_check(startAt, endAt, orderBy, response, key):
    orderBy = orderBy.strip('"\'')
    orderBy = orderBy.split('/')
    if len(orderBy) == 1:
        orderBy = orderBy[0]
    startAt = startAt.strip('"\'') if startAt else None
    endAt = endAt.strip('"\'') if endAt else None
    if startAt and not isinstance(startAt, int):
        if startAt.isnumeric():
            startAt = int(startAt)
    if endAt and not isinstance(endAt, int):
        if endAt.isnumeric():
            endAt = int(endAt)
    startAt_record = []
    for r in response:
        r_copy  = r.copy()
        dict_record = {}
        if orderBy == '$key' or orderBy == '$value':
            if orderBy == '$key':
                dict_record = startAt_endAt_key(startAt, endAt, r, key, dict_record)
            elif orderBy == '$value':
                for d in r:
                    if startAt and endAt:
                        if r[d] >= startAt and r[d] <= endAt: dict_record[d] = r[d]
                    elif startAt:
                        startAt = startAt.strip('"\'')
                        if r[d] >= startAt: dict_record[d] = r[d]
                    else:
                        endAt = endAt.strip('"\'')
                        if r[d] <= endAt: dict_record[d] = r[d]
        else:
            orderBy = orderBy if isinstance(orderBy, list) else [orderBy]
            for i, o in enumerate(orderBy):
                if o in r:
                    if i == len(orderBy) - 1:
                        if not key: ## ./json case
                            if startAt and endAt:
                                if r[o] >= startAt and r[o] <= endAt: dict_record = r_copy
                            elif startAt:
                                if r[o] >= startAt: dict_record = r_copy
                            else:
                                if r[o] <= endAt: dict_record = r_copy
                        else:
                            if startAt and endAt:
                                if r[o] >= startAt and r[o] <= endAt: dict_record[o] = r[o]
                            elif startAt:
                                if r[o] >= startAt: dict_record[o] = r[o]
                            else:
                                if r[o] <= endAt: dict_record[o] = r[o]
                    else:
                        r = r[o]
        if dict_record: startAt_record.append(dict_record)
    return startAt_record

## equalTo filtering
def equalTo_check(equalTo, orderBy, response, key=None):
    equalTo = equalTo.strip('"\'')
    orderBy = orderBy.strip('"\'')
    if equalTo.isnumeric(): equalTo = int(equalTo)
    equalTo_record = []
    for r in response:
        dict_record = {}
        if orderBy == '$key' or orderBy == '$value':
            for d in r:
                if orderBy == '$key':
                    if d == equalTo:
                        dict_record[d] = r[d]
                    elif d == '_id' and r[d] == equalTo:
                        dict_record[equalTo] = r
                elif orderBy == '$value':
                    if key:
                        if r[d] == equalTo and d != key: dict_record[d] = r[d]
                    else:
                        if r[d] == equalTo: dict_record[d] = r[d]
        else:
            orderBy = orderBy.strip('"\'')
            for k in r:
                if isinstance(r[k], dict):
                    if orderBy in r[k]:
                        if r[k][orderBy] == equalTo: dict_record[k] = r[k]
                elif not key: ## /.json case
                    if orderBy == k:
                        if r[k] == equalTo: dict_record[r['_id']] = r
        if dict_record: equalTo_record.append(dict_record)
    return equalTo_record

## limitTo last filttering
def limitToLast_check(limitToLast, sorted_order):
    if len(sorted_order) == 1:
        items = sorted_order[0]
        keys = list(items.keys())
        if len(keys) == 1:
            path = keys[0]
            if isinstance(items[path], dict) or isinstance(items[path], OrderedDict):
                od_items = items[keys[0]].items()
                start = len(od_items)-limitToLast if limitToLast < len(od_items) else 0
                sorted_order = [OrderedDict([(path, OrderedDict(islice(od_items, start, len(od_items))))])]
            elif isinstance(items[path], list):
                if limitToLast >= len(items[path]):
                    sorted_order = [OrderedDict([(path, items[path])])]
                else:
                    od_items = OrderedDict([(k,v) for k, v in enumerate(items[path])]).items()
                    sorted_order = [OrderedDict([(path, OrderedDict(islice(od_items, len(od_items)-limitToLast, len(od_items))))])]
            else:
                sorted_order = None
        else:
            od_items = items.items()
            start = len(od_items)-limitToLast if limitToLast < len(od_items) else 0
            sorted_order = [OrderedDict(islice(items.items(), start, len(od_items)))]
    else:
        sorted_order = sorted_order[len(sorted_order)-limitToLast:]
    return sorted_order

## limitToFirst filtering
def limitToFirst_check(limitToFirst, sorted_order):
    if len(sorted_order) == 1:
        items = sorted_order[0]
        keys = list(items.keys())
        if len(keys) == 1:
            path = keys[0]
            if isinstance(items[path], dict) or isinstance(items[path], OrderedDict):
                od_items = items[keys[0]].items()
                end = limitToFirst if limitToFirst <= len(od_items) else len(od_items)
                sorted_order = [OrderedDict([(path, OrderedDict(islice(od_items, end)))])]
            elif isinstance(items[path], list):
                if limitToFirst >= len(items[path]):
                    sorted_order = [OrderedDict([(path, items[path])])]
                else:
                    od_items = OrderedDict([(k,v) for k, v in enumerate(items[path])]).items()
                    sorted_order = [OrderedDict([(path, OrderedDict(islice(od_items, limitToFirst)))])]
            else:
                sorted_order = None
        else:
            od_items = items.items()
            end = limitToFirst if limitToFirst <= len(od_items) else len(od_items)
            sorted_order = [OrderedDict(islice(items.items(), end))]
    else:
        sorted_order = sorted_order[:limitToFirst]
    return sorted_order

## checking the filtering options and calling appropriate functions
def check_filter_options(orderBy, limitToFirst, limitToLast, startAt, endAt, equalTo, resp, key=None):
    if orderBy:
        sorted_order, res = get_orderBy(orderBy, resp, key)
        if limitToFirst and limitToLast:
            return [{"error" : "orderBy must be a valid JSON encoded path"}]
        if (startAt or endAt) and equalTo:
            return [{ "error" : "equalTo cannot be specified in addition to startAt or endAt"}]
        if limitToFirst:
            sorted_order = limitToFirst_check(limitToFirst, sorted_order)
        if limitToLast:
            sorted_order = limitToLast_check(limitToLast, sorted_order)
        if (startAt or endAt) and sorted_order:
            record = startAt_endAt_check(startAt, endAt, orderBy, sorted_order, key)
            sorted_order = record.copy()
        if equalTo and sorted_order:
            record = equalTo_check(equalTo, orderBy, sorted_order, key)
            sorted_order = record.copy()
        return sorted_order  ## Firebase does not return sorted result
    elif limitToFirst or limitToLast or startAt or endAt or equalTo:
        return [{"error" : "orderBy must be defined when other query parameters are defined"}]
    return resp

## handling GET request
@app.route('/', defaults={'myPath': ''})
@app.route('/<path:myPath>', methods=['GET'])
def catch_all_get(myPath):
    app.json.sort_keys = True
    limitToFirst = request.args.get('limitToFirst', default=None, type=int)
    limitToLast = request.args.get('limitToLast', default=None, type=int)
    startAt = request.args.get('startAt')
    endAt = request.args.get('endAt')
    orderBy = request.args.get('orderBy')
    equalTo = request.args.get('equalTo')
    paths = myPath.split('/')
    if not paths[-1].endswith('.json'): ## if no .json at the end of url return empty
        return ''
    paths[-1] = paths[-1].removesuffix('.json')
    if paths[-1] == '': ## /.json type of url
        paths.pop()
    if paths:
        if len(paths) > 1: ## if paths is longer than 1 then projection is required to select specific data
            path_dict = create_projection(paths[1])
            resp = db.jobs.find({'_id': int(paths[0])}, path_dict) if paths[0].isnumeric() else db.jobs.find({'_id': paths[0]}, path_dict)
        else:
            resp = db.jobs.find({'_id': int(paths[0])}) if paths[0].isnumeric() else db.jobs.find({'_id': paths[0]})
    else: ## empty indicates all the records have to be returned
        resp = db.jobs.find({}).sort('_id')
    if paths:
        resp = check_filter_options(orderBy, limitToFirst, limitToLast, startAt, endAt, equalTo, resp, paths[-1])
    else:
        resp = check_filter_options(orderBy, limitToFirst, limitToLast, startAt, endAt, equalTo, resp)
    if resp:
        resp = list(resp)
    if resp and len(resp) == 1 and {} in resp:
        return ''
    if resp and len(resp) == 1:
        if 'error' not in resp[0]:
            resp = get_response(resp[0], paths) if len(paths) > 1 else resp[0] ## traverse till the path and return the data in that path
        else:
            resp = resp[0]
    if not resp:
        resp = None
    return jsonify(resp) ## sorts the returned json on keys: this is same as the default behaviour of Firebase

## handling PUT request
@app.route('/', defaults={'myPath': ''}, )
@app.route('/<path:myPath>', methods=['PUT'])
def put_data(myPath):
    paths = myPath.split('/')
    if not paths[-1].endswith('.json'):
        return ''
    paths[-1] = paths[-1].removesuffix('.json')
    if paths[-1] == '':
        paths.pop()
    if paths:
        data_request = request.json
        data_request['_id'] = int(paths[0]) if paths[0].isnumeric() else paths[0]
        resp = db.jobs.insert_one(data_request)
    else:
        data_request = request.json
        id = list(data_request.keys())[0]
        data_request['_id'] = int(id) if id.isnumeric() else id
        resp = db.jobs.insert_one(data_request)
    if resp.inserted_id: # checks if at least one document was modified by the update operation
        return 'Data updated successfully'
    else:
        return 'Error: Failed to update data'

## handling PATCH request
@app.route('/', defaults={'myPath': ''}, methods=['PATCH'])
@app.route('/<path:myPath>', methods=['PATCH'])
def patch_data(myPath):
    paths = myPath.split('/')
    if not paths[-1].endswith('.json'):
        return ''
    paths[-1] = paths[-1].removesuffix('.json')
    if paths[-1] == '':
        paths.pop()
    if paths:
        data = request.json
        k = list(data.keys())[0]
        if isinstance(data[k], dict):
            i = list(data[k].keys())[0]
            if not isinstance(data[k][i], dict):
                update_string = k + '.' + i
                req_data= {}
                req_data[update_string] = data[k][i]
                resp = db.jobs.update_one({'_id': int(paths[0])}, {'$set': req_data}) if paths[0].isnumeric() else db.jobs.update_one({'_id': paths[0]}, {'$set': req_data})
            else:
                resp = db.jobs.update_one({'_id': int(paths[0])}, {'$set': request.json}) if paths[0].isnumeric() else db.jobs.update_one({'_id': paths[0]}, {'$set': request.json})
        else:
            resp = db.jobs.update_one({'_id': int(paths[0])}, {'$set': request.json}) if paths[0].isnumeric() else db.jobs.update_one({'_id': paths[0]}, {'$set': request.json})
    else:
        return 'Error: No path specified'
    if resp.modified_count > 0:
        request_info = request.json
        request_info['_id'] = paths[0]
        socketio.emit('updated company info', request.json, namespace='/')
        return 'Data updated successfully'
    else:
        return 'Error: Failed to update data'

## handling POST request
@app.route('/', defaults={'myPath': ''}, methods=['POST'])
@app.route('/<path:myPath>', methods=['POST'])
def post_data(myPath):
    paths = myPath.split('/')
    if not paths[-1].endswith('.json'):
        return ''
    paths[-1] = paths[-1].removesuffix('.json')
    if paths[-1] == '':
        paths.pop()
    data_request = request.json
    data_request['_id'] = str(uuid.uuid4())
    resp = db.jobs.insert_one(data_request)
    if resp.inserted_id: # checks if document was inserted by the insert operation
        return 'Data updated successfully'
    else:
        return 'Error: Failed to update data'

## handling DELETE request
@app.route('/', defaults={'myPath': ''}, methods=['DELETE'])
@app.route('/<path:myPath>', methods=['DELETE'])
def delete_data(myPath):
    paths = myPath.split('/')
    if not paths[-1].endswith('.json'):
        return ''
    paths[-1] = paths[-1].removesuffix('.json')
    if paths[-1] == '':
        paths.pop()
    if paths:
        if len(paths) > 1:
            path_dict = create_projection(paths[1])
            resp = db.jobs.update_one({'_id': int(paths[0])}, {'$unset': path_dict}) if paths[0].isnumeric() else db.jobs.update_one({'_id': paths[0]}, {'$unset': path_dict})
            if resp.modified_count > 0: # checks if at least one document was modified by the update operation
                return 'Data deleted successfully'
            return 'Error: Failed to delete data'
        else:
            resp = db.jobs.delete_one({'_id': int(paths[0])}) if paths[0].isnumeric() else db.jobs.delete_one({'_id': paths[0]})
            if resp.deleted_count > 0:
                return 'Data deleted successfully'
            return 'Error: Failed to delete data'
    else:
        return 'Error: No path specified'

@socketio.on('connect')
def connect(auth):
    print('connected')

if __name__ == '__main__':
    client = MongoClient()
    db = client.project
    socketio.run(app)
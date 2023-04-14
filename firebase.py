# More details at:
#     https://flask.palletsprojects.com/en/2.2.x/

from flask import Flask, jsonify, request
from pymongo import MongoClient
# import json

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

def create_projection(path):
    # path_dict = {path: 1 for path in paths}
    # path_dict['_id'] = 0
    # return path_dict
    return {path: 1, '_id': 0}

def get_response(res_dict, paths):
    for path in paths[1:]:
        res_dict = res_dict[path]
    return res_dict

@app.route('/', defaults={'myPath': ''})
@app.route('/<path:myPath>', methods=['GET'])
def get(myPath):
    paths = myPath.split('/')
    if not paths[-1].endswith('.json'): ## if no .json at the end of url return empty
        return ''
    paths[-1] = paths[-1].removesuffix('.json')
    if paths[-1] == '': ## /.json type of url
        paths.pop()
    if paths[0]:
        if len(paths) > 1: ## if paths is longer than 1 then projection is required to select specific data
            path_dict = create_projection(paths[1])
            resp = db.jobs.find({'_id': int(paths[0])}, path_dict)
        else:
            resp = db.jobs.find({'_id': int(paths[0])}, {'_id': 0})
    else:
        resp = db.jobs.find({}, {'_id': 0})
    resp = list(resp)
    if len(resp) == 1 and {} in resp:
        return ''
    if len(resp) == 1:
        resp = get_response(resp[0], paths) if len(paths) > 1 else resp[0] ## traverse till the path and return the data in that path
    return jsonify(resp)

if __name__ == '__main__':
    client = MongoClient()
    print(client)
    db = client.project
    print(db)
    app.run(debug=True)
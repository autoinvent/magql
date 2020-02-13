import json

from .flask_magql_utils import place_files_in_operations


def parse_request(request):
    if request.mimetype == "multipart/form-data":
        operations = json.loads(request.form.get("operations", "{}"))
        files_map = json.loads(request.form.get("map", "{}"))

        # return {
        #     "query": form["query"],
        #     "variables": json.loads(form["variables"]),
        #     "files": request.files,
        # }

        return place_files_in_operations(operations, files_map, request.files)

    else:
        return request.get_json()

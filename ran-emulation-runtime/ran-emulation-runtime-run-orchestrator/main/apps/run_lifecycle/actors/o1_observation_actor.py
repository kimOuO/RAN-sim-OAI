import json

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.run_lifecycle.services.optional import platform_clients
from main.apps.run_lifecycle.services.optional.o1_observation import read_o1
from main.utils.response import error_response, success_response


class O1ObservationReader:
    @staticmethod
    @csrf_exempt
    @require_http_methods(['POST'])
    def read(request):
        try:
            payload = json.loads(request.body or b'{}')
            run_uuid = str(payload.get('scene_run_uuid') or '')
        except (json.JSONDecodeError, AttributeError) as exc:
            return error_response('Invalid JSON', str(exc), 400)
        if not run_uuid:
            return error_response('Validation failed', {'scene_run_uuid': 'required'}, 400)
        try:
            tree = platform_clients.read_full_tree(run_uuid)
            if not tree.get('success'):
                return error_response('Run not found', run_uuid, 404)
            return success_response(read_o1(run_uuid, tree=tree.get('data')), 'ok', 200)
        except Exception as exc:
            return error_response('O1 狀態讀取失敗', str(exc), 502)

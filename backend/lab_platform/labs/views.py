from django.shortcuts import render
import uuid, json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .docker_manager import create_lab_instance, stop_and_remove, exec_in_container
from django.views import View
from django.views.decorators.http import require_GET
import threading

@csrf_exempt
@require_GET
def start_lab(request):
    # Get lab ID from query parameter (optional)
    lab_id = request.GET.get('lab', 'lab-01-3am-crash')
    sid = str(uuid.uuid4())[:8]
    result = {}
    error = None

    def run():
        try:
            container = create_lab_instance(sid, lab_id)
            result["container_name"] = container.name
            result["success"] = True
        except Exception as e:
            result["error"] = str(e)
            result["success"] = False

    t = threading.Thread(target=run)
    t.start()
    t.join(timeout=5)  # Increased timeout to 5 seconds

    if "success" not in result:
        return JsonResponse({
            "error": "container startup taking too long or failed",
            "session_id": sid
        }, status=500)
    
    if not result.get("success", False):
        return JsonResponse({
            "error": result.get("error", "Unknown error creating container"),
            "session_id": sid
        }, status=500)

    if "container_name" not in result:
        return JsonResponse({
            "error": "container created but name not available",
            "session_id": sid
        }, status=500)

    return JsonResponse({
        "session_id": sid,
        "container_name": result["container_name"],
        "lab_id": lab_id
    })

@csrf_exempt
def reset_lab(request):
    body = json.loads(request.body)
    name = body.get("container_name")
    stop_and_remove(name)
    return JsonResponse({"status": "reset done"})

@csrf_exempt
def validate_lab(request):
    body = json.loads(request.body)
    name = body.get("container_name")
    # run validator script inside container
    out = exec_in_container(name, ["/bin/bash", "/opt/validator/validator.sh"])
    # exec_start returns bytes; decode
    out_text = out.decode() if isinstance(out, (bytes, bytearray)) else str(out)
    ret = {"result": out_text}
    return JsonResponse(ret)

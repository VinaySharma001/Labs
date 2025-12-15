from django.shortcuts import render, get_object_or_404

def home(request):
    return render(request, 'index.html')

def terminal(request, container_name):
    return render(request, 'terminal.html', {'container_name': container_name})

# labs/docker_manager.py
import docker
import time
import os
from pathlib import Path

client = docker.from_env()

# Base directory for labs (adjust path as needed)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
LABS_DIR = BASE_DIR / "labs"

def create_lab_instance(session_id, lab_id="lab-01-3am-crash"):
    """
    Create a lab container instance.
    
    Args:
        session_id: Unique session identifier
        lab_id: Lab identifier (e.g., 'lab-01-3am-crash')
    
    Returns:
        Container object
    """
    name = f"lab01_{session_id}"
    
    # Check if lab has a dockerfile
    lab_path = LABS_DIR / lab_id
    dockerfile_path = lab_path / "dockerfile"
    
    if dockerfile_path.exists():
        # Build image from dockerfile
        try:
            image_tag = f"{lab_id}:latest"
            # Check if image already exists
            try:
                client.images.get(image_tag)
            except docker.errors.ImageNotFound:
                # Build the image
                print(f"Building image for {lab_id}...")
                client.images.build(
                    path=str(lab_path),
                    dockerfile=str(dockerfile_path),
                    tag=image_tag,
                    rm=True
                )
            
            # Run container from built image
            container = client.containers.run(
                image_tag,
                name=name,
                command="sleep infinity",
                stdin_open=True,
                tty=True,
                detach=True,
                ports={'8080/tcp': None}  # Expose port if needed
            )
        except Exception as e:
            print(f"Error building/running lab image: {e}")
            # Fallback to ubuntu
            container = client.containers.run(
                "ubuntu:22.04",
                name=name,
                command="sleep infinity",
                stdin_open=True,
                tty=True,
                detach=True
            )
    else:
        # Fallback to basic ubuntu container
        container = client.containers.run(
            "ubuntu:22.04",
            name=name,
            command="sleep infinity",
            stdin_open=True,
            tty=True,
            detach=True
        )
    
    return container

def stop_and_remove(name):
    try:
        c = client.containers.get(name)
        c.stop(timeout=2)
        c.remove()
    except docker.errors.NotFound:
        pass

def exec_in_container(name, cmd, stream=False):
    c = client.containers.get(name)
    exec_id = client.api.exec_create(c.id, cmd, tty=True)
    output = client.api.exec_start(exec_id, detach=False, tty=True, stream=stream)
    return output

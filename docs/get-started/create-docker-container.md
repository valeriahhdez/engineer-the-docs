# Create your first Docker container

Docker makes it easy to package your application with everything it needs to run no matter where it’s deployed.
The goals of this tutorial are the followingL

1. To build, name, and version your first Docker container.
2. To understand the basic concepts behing Docker containers.

## Why use Docker?

Docker is a software platform that simplifies the process of building, sharing, and running applications. It allows developers to package an application and all its dependencies into a standardized unit called a container. Docker isolates your application and its dependencies from your host system. This means that you can develop and test in a consistent environment that behaves exactly the same on any machine.

Instead of manually installing tools or libraries, you define everything inside a Docker image, which is a portable, self contained environment. 

??? info

    In the context of technology and software development, "to package" means to bundle an application's code, all its dependencies, configuration files, and necessary resources into a single, standardized, and easily distributable unit. 📦
    
    This process is essentially preparing the software for its final journey to the user or server where it will run.

## Key concepts: images vs containers

In Docker, images and containers are close concepts but they serve different purposes. Below is a tale that summarizes the key differences:

| Concept      | Description                          |
| :----------- | :------------------------------------ |
| Image       | A read-only template containing your application, libraries, and dependencies.|
| Container   | A runnable instance of an image. Docker adds a writable layer on top so you can modify it while it runs.|

Each container you start is based on an image, but containers are temporary; images are the reusable blueprint.

## Understanding Docker image names

A full Docker image name follows this structure:

``` 
REGISTRY/NAMESPACE/REPOSITORY:TAG
```

| Component    | Example     | Description    |
| :----------- | :---------- | :---------- |
| Registry      | `docker.io` | Where the image is stored (Docker Hub by default). |
| Namespace/User    |`johndoe`  | Your Docker Hub username or organization.  |
| Repository        | `myapp`   | The name of your project or image.    |
| Image tag               | `v1.0.01`  | Identifies the version or environment (e.g., latest, dev, prod). |

Example:
``` title="bubble_sort.py"
docker.io/janedoe/myapp:v1.0.0
```
When you omit the registry or tag, Docker assumes `docker.io` and `:latest`.

## Create your first Docker container

Let’s start a simple container using an existing image from Docker Hub.

``` 
docker run -d -p 8080:80 --name my-welcome-app docker/welcome-to-docker
```
What this command does:
	•	-d → Runs the container in the background (detached mode).
	•	-p 8080:80 → Maps port 80 inside the container to port 8080 on your computer.
	•	--name my-welcome-app → Assigns a friendly name to the container.
	•	docker/welcome-to-docker → The image to run.

Now open your browser and visit http://localhost:8080 — you should see Docker’s welcome page!

## Build and tag your image

After your container is running, you can capture its state as a new image.
For example, if you made changes inside the container, use:

``` 
docker commit my-welcome-app janedoe/myapp:v1.0.0
```
This command:
	1.	Creates a new, immutable image layer from the container’s current state.
	2.	Assigns the tag v1.0.0 to that new image.

You can now reuse, share, or deploy this image anywhere.

## Version your Docker image

Tags let you organize and track different image versions.
Use semantic versioning to clearly label builds and stages of your workflow:

| Tag | Purpose |
|:---- | :---- |
| `:dev` | Development environment (local testing.) |
| `:staging` | Pre-production testing.|
| `:prod` | Production-ready image. |
| `:v1.0.0`, `:v1.0.1` | Specific, versioned releases.| 

Using explicit tags prevents confusion and allows instant rollback.
For example, if a new deployment fails, you can quickly revert to the previous version:

```
docker run -d -p 8080:80 janedoe/myapp:v1.0.0
```

???+ tip
    Avoid the `:latest` tag for production as it can be overwritten easily.
# Create your first Docker container

Docker makes it easy to package your application with everything it needs to run no matter where it’s deployed.
The goals of this tutorial are the following:

1. To build, name, and version your first Docker container.
2. To understand the basic concepts behing Docker containers.

## Prerequisites

- This tutorials assumes basic familiarity with the command line interface (CLI). 
- To follow this tutorial, you need to have a [Docker account](http://docs.docker.com/accounts/create-account/). 

## Why use Docker?

Docker is a software platform that simplifies the process of building, sharing, and running applications. It allows developers to package an application and all its dependencies into a standardized unit called a _container_. Docker isolates your application and its dependencies from your host system. This means that you can develop and test in a consistent environment that behaves exactly the same on any machine.

Instead of manually installing tools or libraries, you define everything inside a Docker _image_, which is a portable, self contained environment. 

??? info

    In the context of technology and software development, "to package" means to bundle an application's code, all its dependencies, configuration files, and necessary resources into a single, standardized, and easily distributable unit. 📦
    
    This process is essentially preparing the software for its final journey to the user or server where it will run.

## Key concepts: images vs containers

In Docker, images and containers are close concepts but they serve different purposes. Below is a table that summarizes the key differences:

| Concept      | Description                          |
| :----------- | :------------------------------------ |
| Image       | A read-only template containing your application, libraries, and dependencies.|
| Container   | A runnable instance of an image. Docker adds a writable layer on top so you can modify it while it runs.|

Each container you start is based on an image. Containers are temporary, while images are the reusable blueprint. More importantly, images are immutable. Every time you modify your environment dependencies, you must point to a new image version. For this reason, it is a best practice to use semantic versioning ([SemVer](https://semver.org/)) for tagging Docker images.  

A full Docker image name follows this structure:
``` 
REGISTRY/NAMESPACE/REPOSITORY:TAG
```

| Component    		| Example     | Description    |
| :----------- 		| :---------- | :---------- |
| Registry      	| `docker.io` | Where the image is stored (Docker Hub by default.) |
| Namespace/User    |`johndoe`    | Your Docker Hub username or organization.  |
| Repository        | `myapp`     | The name of your project or image.    |
| Image tag         | `v1.0.01`   | Identifies the version or environment (e.g., latest, dev, prod.) |

Example:
``` title="bubble_sort.py"
docker.io/janedoe/myapp:v1.0.0
```

By tagging your images with SemVer, you ensure everyone in your team uses the same version of the image and allows you to roll back to a known, stable version tag if issues are discovered.

## Create a Docker image

### Prerequisites

To create a Docker image, you need to have a repository. Follow these steps to create one, if you don't have it already. 

1. Go to [Docker Hub](https://hub.docker.com/). 
1. Select **Create repository.**
1. Enter the following information:
	- Repository name. Example: `my-app`.
	- (Optional) Short description: It is recommended to add a description that answers key questions about your image "What is this, and why should I use it?" Example: _Container for the "User Authentication" microservice. Built using Node.js 20 and optimized for production deployment._
	- Visibility: Select **Public** if you want others to find and pull your image. 
1. Select **Create.**

### Build and push an image

1. Locate yourself within the directory that contains the project you want a create an image for. 
```
cd YOUR_WORKING_DIRECTORY
# Example: cd my-working-dir
```

2. Build the image with the following command. Change `DOCKER_USERNAME` with your username
```
docker build -t DOCKER_USERNAME/YOUR_APP .
# Example: docker build -t johndoe/my-app:0.1.0 . 
```

??? tip
	Version your image with SemVer.

3. Verify that the image exists locally:
```
docker image ls
```
This should output something similar to this:
```
REPOSITORY                          TAG       IMAGE ID       CREATED          SIZE
johndoe/my-app 					    0.1.0    1503255b9281   2 minutes ago    1.12GB
...
```

4. Push the image to your Docker repository with the `docker push` command. Replace the placedholder `DOCKER_USERNAME/YOUR_APP` with your username and project name, respectively. 
```
docker push DOCKER_USERNAME/YOUR_APP
## Example: docker push johndoe/my-app
```

## Run a container

Let’s start a simple container using an existing image from Docker Hub.
``` 
docker run -d -p 8080:80 --name my-welcome-app docker/welcome-to-docker
```
What this command does:
	-	-d → Runs the container in the background (detached mode).
	-	-p 8080:80 → Maps port 80 inside the container to port 8080 on your computer.
	-	--name my-welcome-app → Assigns a friendly name to the container.
	-	docker/welcome-to-docker → The image to run.

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
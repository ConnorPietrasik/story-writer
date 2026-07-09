# Story Writer

A toy project to familiarize myself with llama.cpp and ComfyUI local APIs. Not particularly useful, but pretty fun 

## How It Works

Because LLMs have a limited output length per prompt, it first generates an outline, then counts the chapters, then generates each chapter individually. Once all the chapters are generated, if images are required it goes through and generates prompts. It then closes the LLM process before saving the generated story (and adding HTML stuff if that's the requested filetype). The next step (if images are enabled) is to launch ComfyUI, send all the the prompts, and finally move the generated images into the story folder.

## Example

The story folder has an example of it working, although I deleted 3/4 of the images to avoid wasting space. The stories themselves aren't great (probably because I'm using Qwen), but the images usually end up pretty cool (especially the eldritch abominations, whether that's the goal or not)
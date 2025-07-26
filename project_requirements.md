# Project overview
This project is focussed on analyzing a beach volley video analyze how many digs, sets, blocks, aces and spikes 
were made by each player.

# AI Agent
You are an expert Computer Vision and Python developer specializing in sports analytics and video processing. 
Your primary objective is to deliver high-quality, production-ready, and well-validated code that accurately 
analyzes beach volleyball videos.

Before beginning to write code, you must generate a detailed, step-by-step implementation plan for addressing both 
functional and technical requirements. This plan should outline:
- Your chosen approach for each computer vision task (ball detection, player detection, player tracking, action recognition).
- Specific libraries or models you intend to use for these tasks (e.g., YOLO for object detection, MediaPipe for pose estimation).
- How you plan to integrate these components and manage the overall video processing pipeline.
- Any potential challenges you anticipate (e.g., occlusions, varying video quality) and your proposed strategies to mitigate them.

After writing or modifying any significant code segment, you must automatically run the unit tests. If any tests 
fail, you are required to iteratively debug and fix the code until all tests pass. For the functional requirements, 
consider how you will internally validate the accuracy of ball, player, and action recognition (e.g., by logging 
intermediate outputs or analyzing a few sample frames).

You are authorized to leverage established open-source computer vision libraries and pre-trained models for recognition
and tracking tasks (e.g., OpenCV, PyTorch/TensorFlow with models like YOLO, PoseNet, or MediaPipe). Justify your choice
of primary computer vision framework/library in your initial plan.

# Technical Requirements
1. **Python Version**: Ensure Python 3.11 or higher is used.
2. Install requirements using uv
3. **Virtual Environment**: Use a virtual environment for dependency management, located at the 
root of the project as venv
4. **Code Style**: Follow PEP 8 guidelines for Python code style.
5. **Documentation**: All functions and classes must be fully documented with docstrings.
6. **Unit Tests**: Write unit tests for all new code, ensuring high test coverage.
7. **Type Hints**: Use type hints for all functions and methods to improve code clarity and maintainability.
8. **Logging**: Implement logging for debugging and monitoring purposes.
9. **Error Handling**: Implement robust error handling to manage exceptions gracefully.
10. **Dependency Management**: Use a pyproject.toml file to manage project dependencies.
11. **Git Practices**: Follow best practices for Git, commit after each logical change, and use descriptive commit
messages.
12. **Code Quality**: Ensure the code is clean, modular, and follows best practices for maintainability.
13. **Performance**: Optimize the code for performance, especially in video processing tasks.
14. **Code Generation**: Do not create more than one file at a time, wait for the user to ask for more files or continue
15. **Code testing**: Aside from unit tests, you can use the resources folder with example videos to test the code.


# Functional Requirements
1. This project shall have a main file that serves as the entry point.
2. The project shall be able to recognize where the ball is in all frames of the video.
3. The project shall be able to recognize where the players are in all frames of the video.
4. The project shall be able to keep track of the same player across all frames of the video.
5. The project shall be able to recognize the actions of the players in all frames of the video.
6. The actions to be recognized are:
   - Digs
   - Sets
   - Blocks
   - Aces
   - Spikes
7. The project shall be able to count the number of each action made by each player.
8. The project shall be able to output the results in a CSV format and a PNG with graphs showing the 
number of each action made by each player.
9. The project must consider edge cases and common challenges in video analysis, such as:
   - Player Occlusion: How will the system handle players obscuring each other or the ball?
   - Lighting and Background Variations: How will the system perform across different outdoor lighting conditions or court backgrounds?
   - Action Nuance: How will the system differentiate between similar actions (e.g., a "set" vs. a "dig" if the trajectory is ambiguous)?
   - Multiple Players: Confirm the system handles tracking and attributing actions to each player in a 2-player or multi-player setup.
10. The PNG output (summary_graphs.png) must contain at least two distinct and clearly labeled visualizations:
   - A bar chart showing the total count of each action type (Digs, Sets, Blocks, Aces, Spikes) across the entire video.
   - A stacked bar chart or individual bar charts displaying the breakdown of each action type per player.
   - Ensure graphs have appropriate titles, axis labels, legends, and are visually appealing for presentation. 
Use standard data visualization libraries like Matplotlib or Seaborn.

# Deliverables & Specifications
1. Functional Codebase: A complete Python project adhering to all technical requirements, capable of processing beach 
volleyball videos.
2. Quantitative Analysis Output: A CSV file (results.csv) detailing the counts of each action (Digs, Sets, Blocks, 
Aces, Spikes) per player, for all analyzed videos
3. Visual Summary Output: A PNG image (summary_graphs.png) containing clearly labeled graphs visualizing the action 
counts per player, ensuring readability and accuracy.
4. Validation Report: A markdown or text file (validation_report.md) detailing the results of internal validation steps,
including unit test coverage reports and any observations/assumptions made during visual verification of player/ball 
detection and action recognition on sample frames.
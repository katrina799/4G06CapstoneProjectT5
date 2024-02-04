# Notes when running Flask app
> **Important Note:**  
> Please connect to the `Dev Container` first before any development

- To run the app, inside the terminal:
    1. Properly set environment variables `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` so we could access our `AWS S3` bucket before running the app. (Note that rebuilding the `Dev Container`` will lose these variables so you have to reset them in that case)
        - For exmaple, run `export AWS_ACCESS_KEY_ID=[key_id_value]` where `[key_id_value]` is the actual value of the `AWS_ACCESS_KEY_ID`
    2. Properly set environment variables `OPENAI_API_KEY` before running the app, so we could send request from `OpenAI API` and access the response from the API.
        - For exmaple, run `export OPENAI_API_KEY=[key_id_value]` where `[key_id_value]` is the actual value of the `OPENAI_API_KEY`
    3. Navigate to the `src` directory by running `cd src/`
    4. Run `export FLASK_DEBUG=1` to set the mode as debug
    5. Run `python -m flask run`
- To open the app,
    1. Navigate to webpage using proper URL inside a browser, for exmaple, the URL could be `http://127.0.0.1:5000/` when accessing the main page of the app if testing locally
        - Alternatively, if developing using *VSCode*, there will be a pop-up on the bottom right saying that our application is avaliable. Click `Open in Browser` to open the web app
- To close the running server, press `CTRL+C` inside the terminal
> **Note:**  
> Please reupload `poc-data/mock_data_poc.csv` to our `AWS S3` after development as changing username or adding/removing courses will overwrite the file stored in `AWS S3`. Instruction on how to upload mock data is [here](https://github.com/wangq131/4G06CapstoneProjectT5/blob/main/src/poc-data/README.md)
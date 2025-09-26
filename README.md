** Description **

Talk To Your Data is designed to enable HICV business users and stakeholders to communicate with the enterprise data via a chat-like interface.

Upon asking a business question, the application looks into the relevant data from the database and generates insights and charts on the retrived data.

Current features also include forecasting business parameters like future sales, units that will be sold and also predicting the likelihood of events like - the event of customers buying tours or time-shares.

Note : This initiative is at its POC stage.


** How to run the application **

Clone the git repository.

1. Create python venv with requirement.txt
- In VS Code : View>Command Pallete>
- In the pallete search and select - Python: Create Environment
- Choose Venv
- Choose the default python interpreter
- Select the requirement.txt from the available files

2. Once the venv is created, open Terminal in VS Code.
3. Run the below bash cmd in terminal:
> streamlit run app.py

The application will automatically open in the browser or click on the url provided in the terminal after running the bash command.

Note : This application will run only when connected to VPN.
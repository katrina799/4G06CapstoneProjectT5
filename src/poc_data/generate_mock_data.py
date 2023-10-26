import pandas as pd
import os

filename = "mock_data_poc.csv"
mock_data = {
    "user_id": [1, 2, 3],
    "username": ["Jane", "Katrina", "Joyce"],
    "courses": [
        ["SE4G06", "SE4X03", "ANTHROP1AA4"],
        ["SE4G06", "STAT3Y03"],
        ["SE4G06", "SE4X03", "MUSIC2MT3", "ENG1A03"],
    ],
}
df = pd.DataFrame(data=mock_data)
df.to_csv(f"{os.getcwd()}/{filename}", header=None)

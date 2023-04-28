# dsci551-emulate-firebase

## To run Firebase(Flask server):
python firebase.py

## To run app(Streamlit): 
cd app \
streamlit run frontend.py

## To import data to mongodb 
cd data \
mongoimport --file jobs_data.json --db project --collection jobs --jsonArray


from app import app
from flask import request, jsonify, render_template
from sodapy import Socrata
import pandas as pd

NYC_API_KEY = "your_key_here"

# setup NYC data connection
client = Socrata("data.cityofnewyork.us", NYC_API_KEY)
# TO-DO: auto-pull these eventually
nycZipcodes = [10453, 10457, 10460, 10458, 10467, 10468, 10451, 10452, 10456, 10454,
                10455, 10459, 10474, 10463, 10471, 10466, 10469, 10470, 10475, 10461,
                10462, 10464, 10465, 10472, 10473, 11212, 11213, 11216, 11233, 11238,
                11209, 11214, 11228, 11204, 11218, 11219, 11230, 11234, 11236, 11239,
                11223, 11224, 11229, 11235, 11201, 11205, 11215, 11217, 11231, 11203,
                11210, 11225, 11226, 11207, 11208, 11211, 11222, 11220, 11232, 11206,
                11221, 11237, 10026, 10027, 10030, 10037, 10039, 10001, 10011, 10018,
                10019, 10020, 10036, 10029, 10035, 10010, 10016, 10017, 10022, 10012,
                10013, 10014, 10004, 10005, 10006, 10007, 10038, 10280, 10002, 10003,
                10009, 10021, 10028, 10044, 10065, 10075, 10128, 10023, 10024, 10025,
                10031, 10032, 10033, 10034, 10040, 11361, 11362, 11363, 11364, 11354,
                11355, 11356, 11357, 11358, 11359, 11360, 11365, 11366, 11367, 11412,
                11423, 11432, 11433, 11434, 11435, 11436, 11101, 11102, 11103, 11104,
                11105, 11106, 11374, 11375, 11379, 11385, 11691, 11692, 11693, 11694,
                11695, 11697, 11004, 11005, 11411, 11413, 11422, 11426, 11427, 11428,
                11429, 11414, 11415, 11416, 11417, 11418, 11419, 11420, 11421, 11368,
                11369, 11370, 11372, 11373, 11377, 11378, 10302, 10303, 10310, 10306,
                10307, 10308, 10309, 10312, 10301, 10304, 10305, 10314, 11249, 11202]

# TO-DO: Change way these are accessed
# global vars
countLimitA = 0
countLimitB = 0
countLimitC = 0
countLimitD = 0
countLimitF = 0
mapPoints = []

# called on app load to setup data
# returns dataframe of noise complaints, sorted by date descending
def get_noise_complaints():
    print("Getting noise complaints...")
    global countLimitA, countLimitB, countLimitC, countLimitD, countLimitF, mapPoints

    # get data, clear dataframe, and store new data in dataframe
    noiseData = client.get(
        "fhrw-4uyv",
        select="unique_key,created_date,complaint_type,descriptor,latitude,longitude,incident_zip,incident_address,borough",
        where="starts_with(complaint_type, 'Noise')",
        order="created_date DESC",
        limit=10000
    )
    print("API data loaded")

    noiseDF = pd.DataFrame(noiseData)
    print("Converted to df")

    # convert date col, sort by desc
    noiseDF['created_date'] = pd.to_datetime(noiseDF.created_date)
    noiseDF['complaint_freq'] = noiseDF.groupby('incident_zip')['incident_zip'].transform('count')
    noiseDF.sort_values('created_date', ascending=False, inplace=True)

    print("Noise complaints loaded")

    # set globals for grade cutoff
    countLimitA = noiseDF.quantile(.2,'index')[0]
    countLimitB = noiseDF.quantile(.4,'index')[0]
    countLimitC = noiseDF.quantile(.6,'index')[0]
    countLimitD = noiseDF.quantile(.8,'index')[0]
    countLimitF = noiseDF.quantile(1.0,'index')[0]
    print("Limits calcualted")

    # create points for map
    for index, row in noiseDF.head(n=3000).iterrows():
        mapPoints.append(
            {
                'latitude': row['latitude'],
                'longitude': row['longitude'],
                'descriptor': row['descriptor'],
                'date': ("%s" % row['created_date'].strftime("%d, %b %Y"))
            }
        )
    print("Map points added")

    # test length of df
    print(len(noiseDF.index))
    return noiseDF

# load data from API
noiseDF = get_noise_complaints()

@app.route('/map')
def map():
    # returns map populated with globals
    return render_template('map.html', complaints=mapPoints)

@app.route("/terms")
def terms():
    # boring terms, modify
    return render_template('terms.html')

@app.route('/', methods = ['GET'])
def home():
    # return main search page
    return render_template('index.html')

@app.route('/', methods = ['POST'])
def home_search():
    # TO-DO: clean up
    # get zipcode, if not in list return errors
    try:
        zipcode = int(request.form['zipcode'])
        print("Zipcode: %d" % zipcode)
        nullZip = False
    except ValueError:
        zipcode = 0000
        nullZip = True

    # check if zip in NYC city and valid zip
    if not zipcode in nycZipcodes or nullZip:
        return render_template('index.html', error=True, error_code="Zipcode not found")

    # get grade
    grade = get_local_grade(noiseDF, zipcode)

    if grade:
        print("Grade: %s" % grade)

        # get recent complaints
        complaints = get_recent_complaints(noiseDF, zipcode)
        if len(complaints) > 0:
            complaint_strs = []
            for complaint in complaints:
                complaint_str = "%s, %s, %s, %s" % (complaint['complaint_type'], complaint['descriptor'],
                      complaint['incident_address'], complaint['created_date'].strftime("%d, %b %Y"))
                complaint_strs.append(complaint_str)
        else:
            complaint_strs = []

        return render_template('index.html', grade=grade, complaints=complaint_strs, results=True)

    else:
        print("Something went wrong...")
        return render_template('index.html', error=True, error_code="Something went wrong.")

def get_local_grade(noiseDF, zipcode):
    # gets number of complaints for zipcode
    # filter df for increased search speed
    tempDF = noiseDF.loc[noiseDF['incident_zip'] == str(zipcode)]

    freq = 0
    for index, row in tempDF.iterrows():
        if row['incident_zip'] == str(zipcode):
            freq = int(row['complaint_freq'])
            break

    if freq < countLimitA:
        grade = "A"
    elif freq < countLimitB:
        grade = "B"
    elif freq < countLimitC:
        grade = "C"
    elif freq < countLimitD:
        grade = "D"
    elif freq <= countLimitF:
        grade = "F"
    else:
        grade = None

    return grade

def get_recent_complaints(noiseDF, zipcode):
    complaints = []

    # filter df for increased search speed
    tempDF = noiseDF.loc[noiseDF['incident_zip'] == str(zipcode)]

    i = 0
    for index, row in tempDF.iterrows():
        if row['incident_zip'] == str(zipcode):
            complaints.append(
                {
                    'complaint_type': row['complaint_type'],
                    'descriptor': row['descriptor'],
                    'incident_address': row['incident_address'],
                    'created_date': row['created_date']
                }
            )
            # only show 10 most recent
            i += 1
            if i > 9:
                break

    return complaints

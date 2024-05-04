from flask import Flask, render_template, redirect, request, jsonify, flash, session
import mysql.connector
import os
import pandas as pd
import pickle
import matplotlib.pyplot as plt


app = Flask(__name__)
app.secret_key=os.urandom(24)

conn =mysql.connector.connect(host="localhost",user="root",password="",database="dietdata")
cursor = conn.cursor()


data = pd.read_csv("csvFiles/DietChartPlan.csv")


# Load the trained model and label encoders
with open("ModelFile.pkl", "rb") as model_file:
    classifier, label_encoder_DietName, label_encoder_DietType = pickle.load(model_file)


@app.route('/')  #First page that Load
def image():
    return render_template('FirstPage.html')

@app.route('/signup')
def signup():
    return render_template('signupPage.html')


def create_user_table(email):

    create_table_query = """
    CREATE TABLE IF NOT EXISTS `{}` (
        User_Table_id INT AUTO_INCREMENT PRIMARY KEY,
        DietName VARCHAR(255),
        dietType VARCHAR(255),
        image_url VARCHAR(255),
        foodName VARCHAR(255),
        carbs INT(20),
        protein INT(20),
        calories INT(20)
    )
    """.format(email)
    cursor.execute(create_table_query)
    conn.commit()

@app.route('/RegistrationNewUser',methods=["POST"])
def add_user():
    Name = request.form.get('Name')
    Email = request.form.get('Email')
    Password = request.form.get('Password')
    cursor.execute("""INSERT INTO `logindetails`(`Name`, `Email`, `Password`) VALUES ('{}','{}','{}')""".format(Name,Email,Password))
    conn.commit()
    flash('Registered successfully!', 'success')
    create_user_table(Email)
    return redirect('/signup')

@app.route('/UserLogin', methods=['POST'])
def LoginVald():
    Email=request.form.get('Email')
    Password=request.form.get('Password')
    cursor.execute("""SELECT * FROM `logindetails` WHERE `Email` LIKE '{}' AND `Password` LIKE '{}'"""
                   .format(Email,Password))
    users=cursor.fetchall()
    if len(users)>0:
        session['Email']=users[0][2]
        # Create a table for the user if not exists
        create_user_table(Email)
        return render_template('UserMainPage.html')
    else:
        flash('Invalid email or password. Please try again.', 'error')
        return redirect('/signup')


unique_brand_to_image_url = data.drop_duplicates(subset='FoodName').set_index('FoodName')['Image'].to_dict()

@app.route('/BestFoodRecommend', methods=['POST'])
def BestFoodRecommend():
    try:
        DietName = request.form['DietName']
        DietType = request.form['DietType']
        Protein = float(request.form['Protein'])
        Calories = float(request.form['Calories'])

        DietName_encoded = label_encoder_DietName.transform([DietName])[0]
        DietType_encoded = label_encoder_DietType.transform([DietType])[0]

        probabilities = classifier.predict_proba([[DietName_encoded, DietType_encoded, Protein, Calories]])[0]

        food_probabilities = pd.DataFrame({
            'FoodName': classifier.classes_,
            'Probability': probabilities
        })

        # Filtering food names based on DietName and DietType
        filtered_food_names = data[(data['DietName'] == DietName) & (data['DietType'] == DietType)]['FoodName'].unique()

        # Filtering food probabilities to only include food names that match the criteria
        top_10_foods = food_probabilities[food_probabilities['FoodName'].isin(filtered_food_names)]
        top_10_foods = top_10_foods.sort_values(by='Probability', ascending=False).head(10)

        recommended_foods = top_10_foods.to_dict(orient='records')

        # Updating food information with additional details
        for food in recommended_foods:
            food_name = food['FoodName']

            food_protein = data.loc[data['FoodName'] == food_name, 'Protein'].iloc[0]
            food_calories = data.loc[data['FoodName'] == food_name, 'Calories'].iloc[0]
            food_carbs = data.loc[data['FoodName'] == food_name, 'Carbs'].iloc[0]
            food_FoodDescription = data.loc[data['FoodName'] == food_name, 'FoodDescription'].iloc[0]

            # Updating the food dictionary with protein, calories, and carbohydrates
            food['Protein'] = food_protein
            food['Calories'] = food_calories
            food['Carbs'] = food_carbs
            food['FoodDescription'] = food_FoodDescription

            # Assigning image URL to the food dictionary
            image_url = unique_brand_to_image_url.get(food_name, 'Image')
            food['image_url'] = image_url

        return render_template("UserMainPage.html",
                               recommended_foods=recommended_foods,
                               DietName=DietName,
                               DietType=DietType,
                               Protein=Protein,
                               Calories=Calories)

    except Exception as e:
         return render_template("UserMainPage.html", error=str(e))


@app.route('/add_to_log', methods=['POST'])
def add_to_log():
        try:
            data = request.json
            dietName = data['dietName']
            dietType = data['dietType']
            image_url = data['image_url']
            foodName = data['foodName']
            carbs = data['carbs']
            protein = data['protein']
            calories = data['calories']

            email = session.get('Email')
            print("Email retrieved from session:", email)

            query = "INSERT INTO `{}` (dietName,dietType,image_url,foodName,carbs,protein,calories) VALUES (%s, %s, %s, %s, %s, %s, %s)".format(email)
            cursor.execute(query, (dietName,dietType,image_url,foodName, carbs, protein, calories))
            conn.commit()

            return jsonify({'message': 'Data added to log successfully'}), 200

        except Exception as e:
            return jsonify({'error': str(e)}), 500

@app.route('/logout')
def logout():
    session.pop('Email')
    flash('Logout successful!', 'success')
    return redirect('/')

@app.route('/userViewLod')
def userViewLod():

    email = session.get('Email')
    query ="SELECT * FROM  `{}`".format(email)
    cursor.execute(query)
    meals = cursor.fetchall()
    return render_template('ViewLogMeals.html',meals=meals)


@app.route('/backtomainpage')
def backtomainpage():
    return render_template('UserMainPage.html')


healtipdata = pd.read_csv("csvFiles/HealthTipData.csv")
@app.route('/HealthTipsPage')
def HealthTipsPage():
    return render_template('HealthTips.html',healthtips = healtipdata.to_dict('records'))


@app.route('/ComparePage', methods=['GET', 'POST'])
def ComparePage():
    email = session.get('Email')
    query = "SELECT DISTINCT foodName FROM `{}`".format(email)
    cursor.execute(query)
    food_detail = cursor.fetchall()

    if request.method == 'POST':
        food1 = request.form['food1']
        food2 = request.form['food2']

        if food1 == food2:
            error_message = "Please select two different foods for comparison."
            return render_template('ComparePage.html', food_detail=food_detail, error_message=error_message)

        query = "SELECT foodName, dietType, image_url,protein,calories,carbs FROM `{}` WHERE foodName = %s OR foodName = %s".format(email)
        cursor.execute(query, (food1, food2))
        food_details = cursor.fetchall()

        return render_template('ComparePage.html', food_detail=food_detail, food_details=food_details, food1=food1, food2=food2)
    else:
        return render_template('ComparePage.html', food_detail=food_detail)


@app.route('/delete/<int:user_id>')
def delete(user_id):
    email = session.get('Email')
    table_user = email
    query = f"DELETE FROM `{table_user}` WHERE User_Table_id = {user_id}"
    cursor.execute(query)
    conn.commit()
    return redirect('/userViewLod')

@app.route('/SelfAnalyse')
def SelfAnalyse():
    try:
        email = session.get('Email')
        if email:
            maindata_query = "SELECT Name, Email FROM logindetails WHERE Email LIKE %s"
            cursor.execute(maindata_query, (email,))
            userdata = cursor.fetchall()

            sum_query = "SELECT SUM(protein), SUM(calories), SUM(carbs) FROM `{}`".format(email)
            cursor.execute(sum_query)
            sum_data = cursor.fetchone()

            properties = ['Protein', 'Calories', 'Carbs']
            sums = [sum_data[0], sum_data[1], sum_data[2]]

            # Create the pie chart
            plt.figure(figsize=(8, 6))
            plt.pie(sums, labels=properties, autopct='%1.1f%%', startangle=140)
            plt.title('Distribution of Nutrients')
            plt.axis('equal')
            pie_chart_path = 'static/pie_chart.png'
            plt.savefig(pie_chart_path)
            plt.close()

            bar_query = "SELECT DietName, dietType FROM `{}`".format(email)
            cursor.execute(bar_query)
            data = cursor.fetchall()

            diet_names = [row[0] for row in data]
            diet_types = [row[1] for row in data]

            # Count occurrences of each diet type
            diet_type_counts = {}
            for diet_type in diet_types:
                if diet_type in diet_type_counts:
                    diet_type_counts[diet_type] += 1
                else:
                    diet_type_counts[diet_type] = 1

            plt.figure(figsize=(10, 6))
            colors = ['skyblue', 'salmon', 'lightgreen', 'red', 'pink', 'yellow']
            plt.bar(diet_type_counts.keys(), diet_type_counts.values(), color=colors)
            plt.xlabel('Diet Type Logged By user')
            plt.ylabel('Frequency Of Food Logged')
            plt.title('Diet Chart')

            # Manually set the y-axis tick positions
            y_ticks = [0,2,4,6,8,10]  # Add more values as needed
            plt.yticks(y_ticks)

            plt.xticks(rotation=45, ha='right')  # Rotate x-axis labels for better readability
            plt.tight_layout()

            plt.savefig('static/bar_chart.png')

            # Render the template with user data and the path to the pie chart
            return render_template('ReportAnalyse.html', userdata=userdata, pie_chart='static/pie_chart.png',
                                   chart_image='static/bar_chart.png')

    except Exception as e:
        print(f"Error: {e}")
        return render_template('error.html', message='An error occurred while fetching data.')


if __name__ == '__main__':
    app.run(debug=True)




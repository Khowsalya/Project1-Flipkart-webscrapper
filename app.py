# doing necessary imports
from flask import Flask, render_template, request
from flask_cors import cross_origin
import re
from bs4 import BeautifulSoup as bs
from urllib.request import urlopen as ureq
import pandas as pd
import pymongo
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io import BytesIO
import base64
import logging

"""Logger to check the database connection"""

DBlogger=logging.getLogger('Database')

DBlogger.setLevel(logging.DEBUG)

formatter=logging.Formatter('%(asctime)s:%(name)s: %(message)s')

file_handler=logging.FileHandler('Database.log')

file_handler.setLevel(logging.ERROR)

file_handler.setFormatter(formatter)

DBlogger.addHandler(file_handler)

"""Stream Handler To Get Logs on console"""

stream_handler=logging.StreamHandler()
stream_handler.setFormatter(formatter)
DBlogger.addHandler(stream_handler)



app = Flask(__name__)  # initialising the flask app with the name 'app'

@app.route('/',methods=['POST','GET']) # route with allowed methods as POST and GET
@cross_origin()
def index():
    if request.method == 'POST':
        searchString = request.form['content'].replace(" ", "-") # obtaining the search string entered in the form
        DBlogger.debug('Requeest Recieved for {}'.format(searchString))

        try:

            dbConn = pymongo.MongoClient(f"mongodb+srv://test1:1234#1234@cluster0.o1209.mongodb.net/sampledb?retryWrites=true&w=majority")  # opening a connection to Mongo
            DBlogger.debug('Successfully Connected with MongoDB !')
            db = dbConn['iNeuron_AI']  # connecting to the database called iNeuron_AI
            reviews = db[searchString].find({}) # searching the collection with the name same as the keyword


            if reviews.count() > 0:

                df = pd.DataFrame(reviews) #converting collection to dataframe
                DBlogger.debug('Found Collection in Database {}'.format(searchString))
                df['new_salesprice'] = df['sales_price'].map(lambda x: re.sub(r'\W+', '', x))
                # df['new_salesprice'] = np.where((df.new_salesprice == "nosalesprice"), 0, df.new_salesprice)
                df['new_salesprice'] = df['new_salesprice'].astype(float).sort_values(ascending=True)

                maxPrice = "Rs." + str(df['new_salesprice'].max()) + "/-"
                minPrice = "Rs." + str(df['new_salesprice'].min()) + "/-"

                df['seller_rating'] = df.seller_rating.str.extract('(\d.\d)', expand=False)
                df['seller_rating'] = df['seller_rating'].astype(float)
                df['seller_rating'] = df['seller_rating'].fillna(0)

                result = df.groupby('seller_name').agg({'seller_rating': "mean"})
                sr = pd.DataFrame(result)
                fd = sr[sr["seller_rating"].between(3.5, 5)]
                fd=fd.add_suffix("").reset_index()

                df['ratings'] = np.where((df.ratings == "no ratings"), 0, df.ratings)
                df['ratings'] = df['ratings'].astype(float)
                df['ratings'] = df['ratings'].sort_values(ascending=True)
                ratings=df['ratings']
                # ranges = [1, 2, 3, 4, 5]
                # df.groupby(pd.cut(df.ratings, ranges)).count()
                img = BytesIO()
                plt.hist(df['ratings'], bins=[1, 2, 3, 4, 5], histtype="bar", rwidth=0.5)
                plt.xlabel('Products_Ratings')
                plt.ylabel("Count_of_Ratings")
                plt.savefig(img, format='png')
                plt.close()
                img.seek(0)
                plot_url = base64.b64encode(img.getvalue()).decode('utf8') #getting chart for ratings
                DBlogger.debug('Got histogram chart for {} ratings'.format(searchString))

                return render_template('plot.html', plot_url=plot_url,data=fd.to_html(),maxPrice=maxPrice,minPrice=minPrice,searchString=searchString)

            else:
                flipkart_url = "https://www.flipkart.com/search?q=" + searchString  # preparing the URL to search the product on flipkart
                DBlogger.info('Hitted the URL  of product {}'.format(searchString))
                uclient = ureq(flipkart_url)  # requesting the webpage from the internet
                flipkartPage = uclient.read()  # reading the webpage
                uclient.close()  # closing the connection to the web server
                flipkart_html = bs(flipkartPage, "html.parser")  # parsing the webpage as HTML

                page_count = []
                for i in flipkart_html.find("div", {"class": "_2MImiq"}):
                    page_count.append(i.text)

                if "," in page_count[0].split(" ")[-1]:
                    prod_count = int(page_count[0].split(" ")[-1].replace(",", ""))
                else:
                    prod_count = int(page_count[0].split(" ")[-1])

                all_prod_link = list()
                for i in range(1, prod_count + 1):  # Number of pages plus one
                    prod_link = "https://www.flipkart.com/search?q={}&page={}".format(searchString, i)
                    all_prod_link.append(prod_link)

                productlinks = list()
                for links in all_prod_link:
                    uclient = ureq(links)  # requesting the webpage from the internet
                    flipkartPage = uclient.read()  # reading the webpage
                    uclient.close()  # closing the connection to the web server
                    flipkart_html = bs(flipkartPage, "html.parser")  # parsing the webpage as HTML
                    for box in flipkart_html.findAll("div", {"class": "_4ddWXP"}):
                        links = "https://www.flipkart.com" + box.a['href']
                        productlinks.append(links)
                    # insert three type url scrapping here
                    for box in flipkart_html.findAll("div", {"class": "_2kHMtA"}):
                        links = "https://www.flipkart.com" + box.a['href']
                        productlinks.append(links)
                    for box in flipkart_html.findAll("div", {"class": "_1xHGtK"}):
                        links = "https://www.flipkart.com" + box.a['href']
                        productlinks.append(links)
                table = db[searchString] #creating new database collection with product name
                DBlogger.info('New collection Created as {}'.format(table))

                products = list()
                for p in productlinks:
                    product = dict()
                    uclient = ureq(p)  # requesting the webpage from the internet
                    flipkartPage = uclient.read()  # reading the webpage
                    uclient.close()  # closing the connection to the web server
                    soup = bs(flipkartPage, "html.parser")  # parsing the webpage as HTML

                    name = soup.find('h1', {'class': 'yhB1nd'})

                    if name is None:
                        product['name'] = 'no product name'
                    else:
                        product['name'] = name.text

                    sales_price = soup.find('div', {'class': '_30jeq3 _16Jk6d'})

                    if sales_price is None:
                        product['sales_price'] = 'no sales price'
                    else:
                        product['sales_price'] = sales_price.text

                    original_price = soup.find('div', {'class': '_3I9_wc _2p6lqe'})

                    if original_price is None:
                        product['original_price'] = 'no original_price'
                    else:
                        product['original_price'] = original_price.text

                    discounts = soup.find('div', {'class': '_3Ay6Sb _31Dcoz'})

                    if discounts is None:
                        product['discounts'] = 'no discounts'
                    else:
                        product['discounts'] = discounts.text

                    ratings = soup.find('div', {'class': '_3LWZlK'})

                    if ratings is None:
                        product['ratings'] = 'no ratings'
                    else:
                        product['ratings'] = ratings.text

                    no_of_ratingsAndreviews = soup.find('span', {'class': '_2_R_DZ'})

                    if no_of_ratingsAndreviews is None:
                        product['no_of_ratingsAndreviews'] = 'no ratings and reviews count'
                    else:
                        product['no_of_ratingsAndreviews'] = no_of_ratingsAndreviews.text.replace("\xa0", " ")


                    available_offer=soup.find('div', {'class': 'XUp0WS'})
                    # available_offer = available_offer.text
                    # available_offer_new = available_offer_old.replace("Offer", "Offer : ")
                    # available_offer_lst = available_offer_new.split("T&C")
                    # available_offer_ast = available_offer_lst[:-1]

                    if available_offer is None:
                        product['available_offer'] = 'sold out'
                    else:
                        product['available_offer'] = available_offer.text


                    if soup.find('div', {'class': '_1RLviY'}):
                        seller = soup.find('div', {'class': '_1RLviY'})
                        seller = seller.text
                        seller_rating = re.sub('[a-zA-Z]', "", seller).replace(" ", "")
                        seller_name = re.sub('[0-9].[0-9]', "", seller)

                        if seller is None:
                            product['seller_name'] = 'no seller name'
                        else:
                            product['seller_name'] = seller_name

                        if seller is None:
                            product['seller_rating'] = 'no seller rating'
                        else:
                            product['seller_rating'] = seller_rating

                    highlights_lst = []

                    highlights = soup.find_all('li', {'class': '_21Ahn-'})

                    for i in range(len(highlights)):
                        highlights_lst.append(highlights[i].text)

                    if len(highlights_lst) == 0:
                        product['highlights'] = 'no highlights'
                    else:
                        product['highlights'] = highlights_lst

                    commentboxes = soup.find_all('div', {
                        'class': "_16PBlm"})  # finding the HTML section containing the customer comments

                    reviews = []  # initializing an empty list for reviews
                    #  iterating over the comment section to get the details of customer and their comments
                    for commentbox in commentboxes:
                        try:
                            name = commentbox.div.div.find_all('p', {'class': '_2sc7ZR _2V5EHH'})[0].text

                        except:
                            name = 'No Name'

                        try:
                            rating = commentbox.div.div.div.div.text

                        except:
                            rating = 'No Rating'

                        try:
                            commentHead = commentbox.div.div.div.p.text
                        except:
                            commentHead = 'No Comment Heading'

                        try:
                            comtag = commentbox.div.div.find_all('div', {'class': ''})
                            custComment = comtag[0].div.text
                        except:
                            custComment = 'No Customer Comment'

                        try:
                            review_age = commentbox.div.div.find_all('p', {'class': '_2sc7ZR'})[1].text
                        except:
                            review_age = 'no review age'

                        mydict = {"Name": name, "Rating": rating, "CommentHead": commentHead, "review_age": review_age,
                                  "Comment": custComment}

                        reviews.append(mydict)

                    if len(reviews) == 0:
                        product['reviews'] = "no reviews"
                    else:
                        product['reviews'] = reviews

                    products.append(product)

                DBlogger.info('product {} details has been successfully appended in list'.format(searchString))

                rec = table.insert_many(products)

                DBlogger.debug("{} Added To {} Collection".format(len(products), table))

                rows = table.find({})
                df = pd.DataFrame(rows)

                df['new_salesprice'] = df['sales_price'].map(lambda x: re.sub(r'\W+', '', x))
                df['new_salesprice'] = np.where((df.new_salesprice == "nosalesprice"), 0, df.new_salesprice)
                df['new_salesprice'] = df['new_salesprice'].astype(float).sort_values(ascending=True)

                maxPrice = "Rs." + str(df['new_salesprice'].max()) + "/-"
                minPrice = "Rs." + str(df['new_salesprice'].min()) + "/-"

                df['seller_rating'] = df.seller_rating.str.extract('(\d.\d)', expand=False)
                df['seller_rating'] = df['seller_rating'].astype(float)
                df['seller_rating'] = df['seller_rating'].fillna(0)

                result = df.groupby('seller_name').agg({'seller_rating': "mean"})
                sr = pd.DataFrame(result)
                fd = sr[sr["seller_rating"].between(3.5, 5)]
                fd = fd.add_suffix("").reset_index()

                df['ratings'] = np.where((df.ratings == "no ratings"), 0, df.ratings)
                df['ratings'] = df['ratings'].astype(float)
                df['ratings'] = df['ratings'].sort_values(ascending=True)
                ratings = df['ratings']
                # ranges = [1, 2, 3, 4, 5]
                # df.groupby(pd.cut(df.ratings, ranges)).count()

                img = BytesIO()
                plt.hist(df['ratings'], bins=[1, 2, 3, 4, 5], histtype="bar", rwidth=0.5)
                plt.xlabel('Products_Ratings')
                plt.ylabel("Count_of_Ratings")
                plt.savefig(img, format='png')
                plt.close()
                img.seek(0)
                plot_url = base64.b64encode(img.getvalue()).decode('utf8')
                DBlogger.debug('Got histogram chart for {} ratings'.format(searchString))

                return render_template('plot.html', plot_url=plot_url,data=fd.to_html(),maxPrice=maxPrice,minPrice=minPrice,searchString=searchString),searchString


        except Exception as e:
            DBlogger.exception(e)


    else:
        # return index page if home is pressed or for the first run
        return render_template("index.html")

@app.route('/quiz_answers',methods=['POST','GET']) # route with allowed methods as POST and GET to show prodcut details
@cross_origin()
def quiz_answers():
    p1 = request.form['minprice']
    p2 = request.form['maxprice']
    r = request.form['rating']
    s = request.form['product']
    rate =[]
    if r=="above 4":
        rate.append(4)
    elif r=="above 3":
        rate.append(3)
    elif r=="above 2":
        rate.append(2)
    else:
        rate.append(1)

    if len(p1) !=0 and len(p2) !=0 and len(r) !=0 and len(s) !=0: #given price range and ratings
        dbConn = pymongo.MongoClient(f"mongodb+srv://test1:1234#1234@cluster0.o1209.mongodb.net/sampledb?retryWrites=true&w=majority")  # opening a connection to Mongo
        DBlogger.debug('Successfully Connected with MongoDB product price_range and ratings !')
        db = dbConn['iNeuron_AI']# connecting to the database called iNeuron_AI
        reviews = db[s].find({})
        data = pd.DataFrame(reviews)
        DBlogger.debug('Found Collection in Database {} for product price_range and ratings'.format(s))
        data['new_salesprice'] = data['sales_price'].map(lambda x: re.sub(r'\W+', '', x))
        data['new_salesprice'] = np.where((data.new_salesprice == "nosalesprice"), 0, data.new_salesprice)
        data['new_salesprice'] = data['new_salesprice'].astype(float)
        data = data.sort_values(by='new_salesprice', ascending=True)
        boolean_findings = data['ratings'].str.contains('no ratings')
        total_occurence = boolean_findings.sum()

        if (total_occurence > 0):
            data['ratings'] = np.where((data.ratings == "no ratings"), 0, data.ratings)
            data['ratings'] = data['ratings'].astype(float)
        else:
            data['ratings'] = data['ratings'].astype(float)

        filter_data = data[data["new_salesprice"].between(float(p1),float(p2))]

        filter_data = filter_data[filter_data['ratings'] > rate[0]]
        filter_data = filter_data.drop(['new_salesprice'], axis=1)
        filter_data=filter_data.drop(['_id'], axis=1)
        return render_template("datatable.html", column_names=filter_data.columns.values,
                               row_data=list(filter_data.values.tolist()), zip=zip)
    elif len(p1) == 0 and len(p2) == 0 and len(r) !=0 and len(s) !=0: #given ratings alone
        dbConn = pymongo.MongoClient(f"mongodb+srv://test1:1234#1234@cluster0.o1209.mongodb.net/sampledb?retryWrites=true&w=majority")  # opening a connection to Mongo
        DBlogger.debug('Successfully Connected with MongoDB  for product_ratings!')
        db = dbConn['iNeuron_AI']  # connecting to the database called crawlerDB
        reviews = db[s].find({})
        data = pd.DataFrame(reviews)
        DBlogger.debug('Found Collection in Database {} for product ratings'.format(s))
        data['new_salesprice'] = data['sales_price'].map(lambda x: re.sub(r'\W+', '', x))
        data['new_salesprice'] = np.where((data.new_salesprice == "nosalesprice"), 0, data.new_salesprice)
        data['new_salesprice'] = data['new_salesprice'].astype(float)
        data = data.sort_values(by='new_salesprice', ascending=True)
        # filter_data = data[data["new_salesprice"].between(p1, p2)]
        boolean_findings = data['ratings'].str.contains('no ratings')
        total_occurence = boolean_findings.sum()

        if (total_occurence > 0):
            data['ratings'] = np.where((data.ratings == "no ratings"), 0, data.ratings)
            data['ratings'] = data['ratings'].astype(float)
        else:
            data['ratings'] = data['ratings'].astype(float)
        filter_data = data[data['ratings'] > rate[0]]
        filter_data = filter_data.drop(['new_salesprice'], axis=1)
        filter_data = filter_data.drop(['_id'], axis=1)
        return render_template("datatable.html", column_names=filter_data.columns.values,
                               row_data=list(filter_data.values.tolist()), zip=zip)
    else:
        return "Sorry!!!!!!!!!Pleas select rating above 1 to get product details "


if __name__ == "__main__":
    # app.run(port=8000,debug=True) # running the app on the local machine on port 8000
    app.run(debug=True)

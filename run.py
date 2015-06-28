from database import init_db, db_session
from flask import Flask
from models import *
import json
from elasticsearch import Elasticsearch

init_db()

app = Flask(__name__)


es = Elasticsearch([{'host': 'localhost', 'port': 9200}])


@app.route('/alldoctors')
def get_all_doctors():
    doctor_data = {}
    doclist=[]
    for d in Doctor.query.all():
    	print d.name
    	doctor_data = {}
    	clinicList = []
    	doctor_data['name'] = d.name
    	doctor_data['id'] = d.id
    	doctor_data['email'] = d.email
    	doctor_data['recommendations']=d.recommendations
    	doctor_data['photo']=d.photo
    	for clinic in d.clinics:
    		clinicMap={}
	    	clinicMap["name"] = clinic.name
	    	clinicMap["address"] = clinic.address
	    	clinicMap["fees"] = assoc_doc_clinic.query.filter(assoc_doc_clinic.doc_id==d.id,
                    assoc_doc_clinic.clinic_id == clinic.id).first().fees
	    	clinicList.append(clinicMap)
    	doctor_data["clinics"] = clinicList
    	doctor_data['specialities'] = [speciality.name for speciality in d.specialities]
    	doclist.append(doctor_data)
    response= {'data': doclist, 'success':True}
    return json.dumps(response)




@app.route('/doctor/<doc_id>')
def get_doctor_profile(doc_id):
    d=Doctor.query.get(doc_id)
    if not d.published:
        return json.dumps({'success':False,'Error':'No such Doctor exists(or is published)'})
    doctor = {}
    doctor['name'] = d.name
    doctor['id'] = d.id
    doctor['email'] = d.email
    doctor['recommendations'] = d.recommendations
    doctor['experience'] = d.experience
    doctor['qualification']=d.qualification
    doctor['locality'] = Locality.query.get(d.locality).name
    doctor['city'] = City.query.get(d.city).name
    doctor['photo'] = d.photo
    doctor['salutation'] = d.salutation
    clinicLists =[]
    for clinic in d.clinics:
        clinicmap = {}
        clinicmap['name'] = clinic.name
        clinicmap['address'] = clinic.address
        clinicmap['fees'] = assoc_doc_clinic.query.filter(assoc_doc_clinic.doc_id==d.id,
                    assoc_doc_clinic.clinic_id == clinic.id).first().fees
        clinicmap['timing'] = assoc_doc_clinic.query.filter(assoc_doc_clinic.doc_id==d.id,
                    assoc_doc_clinic.clinic_id == clinic.id).first().timings
        clinicLists.append(clinicmap)
    doctor['clinics'] = clinicLists
    response= {'data': doctor, 'success':True}
    '''
    for k,v in d.__dict__.iteritems():
      if(k[0]!='_'):
        doctor[k]=v
    response= {'data': d.serialize(), 'success':True}'''
    return json.dumps(response,mimetype = "text/json")
    #return json.dumps(d.__dict__)




@app.route('/allclinics')
def get_all_clinics():
    clinicList = []
    for c in Clinic.query.all():
        clinicmap = {}
        clinicmap['name'] = c.name
        clinicmap['address'] = c.address
        clinicmap['id'] = c.id
        #clinicmap['city'] = City.query.get(c.city).name
        clinicList.append(clinicmap)
    response = {'clinics': clinicList,'success':True}
    return json.dumps(response)

#----------------------------------------------------------------ElasticSearch--------------------------------------------------------------

@app.route('/location/<city>/<location_term>')
def locationsearch(city,location_term):
    '''
    This function is used for (Elastic) searching the hits for a location.
    '''
    res=es.search(index="practo_index", doc_type = "location",
            body={  "query":{
                "filtered":{
                    "query":{
                        "query_string": {
                             "default_field": "name",
                             "query": location_term
                          }
                    },
                    "filter":{
                        "term": {"city": city.lower()}
                    }
                }      
           }
        })
    locality_list = []                                                   
    for loc in res['hits']['hits']:
        print loc
        locality_list.append({"name":loc['_source']['name'], "type": "Locality"})
    response = {}
    response={"total":res['hits']['total'],"matches":locality_list}
    return json.dumps(response)

@app.route('/query/<city>/<query_term>')
def homequery(city,query_term):
    '''
    This function is used for Elastic search of query, which can be the name 
        of a doctor , clinic, or speciality.      '''

    res=es.search(index="practo_index", 
    body={  "query":{
                "filtered":{
                    "query":{
                        "query_string": {   
                            "query":query_term
                        }
                    },
                    "filter":{
                        "term": {"city": city.lower()}
                    }
                }      
           }
        })
    hitlist=[]
    print res
    for hit in res['hits']['hits']:

        if hit['_type']=="doctors":
            hitlist.append({"name":hit['_source']['name'], "type" : "doctor"})

        if hit['_type']=="clinics":
            hitlist.append({"name":hit['_source']['name'],"type" : "clinic"})

        if hit['_type']=="specialities":
            hitlist.append({"name":hit['_source']['name'],"type" : "specialities"})
    response = {"total":res['hits']['total'],"matches" : hitlist}
    return json.dumps(response)

#---------------------------------------------------------------------Querying---------------------------------------------------------------

@app.route('/<city_term>/<query_term>')
def SearchSpecLocation(city_term,query_term):
    
    jsonresult= homequery(location_term,query_term)

@app.route('/<location_term>/<query_term>/<spec_term>')
def getMoreSearch(location_term,query_term):
    jsonresult= homequery(location_term,query_term)

#-----------------------------------------------------------------------End of Views----------------------------------------------------------


if __name__ == '__main__':
	app.secret_key = 'super secret35796Shreysfjkhogh08923epuoij'
	app.run(host = 'localhost',port = 8000,debug=True)
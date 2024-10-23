from db_config import client
def connect_to_mongodb():
    # Send a ping to confirm a successful connection
    try:
        client.admin.command('ping')
        print("You successfully connected to MongoDB!")
    except Exception as e:
        raise Exception("Error: ",e)

import boto3
import nexmo
import uuid
from flask import Flask, request
app = Flask(__name__)
app.config.from_pyfile('.env')
sqs = boto3.client('sqs')


@app.route('/')
def index():
    return "Success! Endpoints available: /add and /process."


# store an SMS message to SQS FIFO for later sending
@app.route('/add', methods=['POST'])
def add():

    if request.method == 'POST':
        message = request.get_json()
        response = sqs.send_message(
            QueueUrl=app.config.get('AWS_SQS_URL'),
            MessageAttributes={
                'from': {
                    'DataType': 'String',
                    'StringValue': message['from']
                },
                'to': {
                    'DataType': 'String',
                    'StringValue': message['to']
                }
            },
            MessageBody=(
                message['message']
            ),
            MessageDeduplicationId=str(uuid.uuid1()),
            MessageGroupId=str(uuid.uuid1())
        )

    if response['MessageId']:
        return "MessageId: " + response['MessageId']
    else:
        return "Error: " + response["error_text"]


# process the SQS messages 1/second
@app.route('/process')
def process():
    # get the next message in the queue to send
    message = sqs.receive_message(
        QueueUrl=app.config.get('AWS_SQS_URL'),
        AttributeNames=[
            'SentTimestamp'
        ],
        MessageAttributeNames=[
            'All'
        ],
        MaxNumberOfMessages=1,
        VisibilityTimeout=1,
        WaitTimeSeconds=1
    )

    # send the message
    if message.get("Messages"):
        client = nexmo.Client(app.config.get('VONAGE_API_KEY'), app.config.get('VONAGE_API_SECRET'))
        response = client.send_message(
            {
                "from": message["Messages"][0]["MessageAttributes"]["from"]["StringValue"],
                "to": message["Messages"][0]["MessageAttributes"]["to"]["StringValue"],
                "text": message["Messages"][0]["Body"]
            }
        )
    else:
        return "Queue empty!"

    # return status messages and delete from queue
    if response["messages"][0]["status"] == "0":
        # Delete message from the queue
        sqs.delete_message(
            QueueUrl=app.config.get('AWS_SQS_URL'),
            ReceiptHandle=message["Messages"][0]["ReceiptHandle"]
        )
        return "Message sent and removed from queue, SQS MessageId: " + message["Messages"][0]["MessageId"]
    else:
        return "Error: " + response['messages'][0]['error-text']

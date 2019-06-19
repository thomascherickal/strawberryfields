# Copyright 2019 Xanadu Quantum Technologies Inc.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

r"""
API Client library that interacts with the compute-service API over the HTTP
protocol.
"""

import urllib

import dateutil.parser
import json
import requests


class MethodNotSupportedException(TypeError):
    """
    Exception to be raised when a ResourceManager method is not supported for a
    particular Resource.
    """

    pass


class ObjectAlreadyCreatedException(TypeError):
    """
    Exception to be raised when an object has already been created but the user
    is attempting to create it again.
    """

    pass


class APIClient:
    """
    An object that allows the user to connect to the compute-service API.
    """

    ALLOWED_BASE_URLS = ["localhost"]
    DEFAULT_BASE_URL = "localhost"
    CONFIGURATION_PATH = ""

    def __init__(self, use_ssl=True, base_url=None, **kwargs):
        """
        Initialize the API client with various parameters.
        """
        # TODO: Load username, password, or authentication token from
        # configuration file

        self.USE_SSL = use_ssl
        self.AUTHENTICATION_TOKEN = kwargs.get("authentication_token", "")
        self.HEADERS = {}

        if not base_url:
            self.BASE_URL = self.DEFAULT_BASE_URL
        elif base_url in self.ALLOWED_BASE_URLS:
            self.BASE_URL = base_url
        else:
            raise ValueError("base_url parameter not in allowed list")

    def load_configuration(self):
        """
        Loads username, password, and/or authentication token from a config
        file.
        """
        raise NotImplementedError()

    def authenticate(self, username, password):
        """
        Retrieve an authentication token from the server via username
        and password authentication.
        """
        raise NotImplementedError()

    def set_authorization_header(self, authentication_token):
        """
        Adds the authorization header to the headers dictionary to be included
        with all API requests.
        """
        self.headers["Authorization"] = authentication_token

    def join_path(self, path):
        """
        Joins a base url with an additional path (e.g. a resource name and ID)
        """
        return urllib.parse.urljoin(f"{self.BASE_URL}/", path)

    def get(self, path):
        """
        Sends a GET request to the provided path. Returns a response object.
        """
        return requests.get(url=self.join_path(path), headers=self.HEADERS)

    def post(self, path, payload):
        """
        Converts payload to a JSON string. Sends a POST request to the provided
        path. Returns a response object.
        """
        data = json.dumps(payload)
        return requests.post(url=self.join_path(path), headers=self.HEADERS, data=data)


class ResourceManager:
    """
    This class handles all interactions with APIClient by the resource.
    """

    http_status_code = None

    def __init__(self, resource, client=None):
        """
        Initialize the manager with resource and client instances . A client
        instance is used as a persistent HTTP communications object, and a
        resource instance corresponds to a particular type of resource (e.g.
        Job)
        """
        setattr(self, "resource", resource)
        setattr(self, "client", client or APIClient())

    def join_path(self, path):
        """
        Joins a resource base path with an additional path (e.g. an ID)
        """
        return urllib.parse.urljoin(f"{self.resource.PATH}/", path)

    def get(self, job_id):
        """
        Attempts to retrieve a particular record by sending a GET
        request to the appropriate endpoint. If successful, the resource
        object is populated with the data in the response.
        """
        if "GET" not in self.resource.SUPPORTED_METHODS:
            raise MethodNotSupportedException("GET method on this resource is not supported")

        response = self.client.get(self.join_path(str(job_id)))
        self.handle_response(response)

    def create(self, params):
        """
        Attempts to create a new instance of a resource by sending a POST
        request to the appropriate endpoint.
        """
        if "POST" not in self.resource.SUPPORTED_METHODS:
            raise MethodNotSupportedException("POST method on this resource is not supported")

        if self.resource.id:
            raise ObjectAlreadyCreatedException("ID must be None when calling create")

        response = self.client.post(self.resource.PATH, params)

        self.handle_response(response)

    def handle_response(self, response):
        """
        Store the status code on the manager object and handle the response
        based on the status code.
        """
        self.http_status_code = response.status_code
        if response.status_code in (200, 201):
            self.handle_success_response(response)
        else:
            self.handle_error_response(response)

    def handle_success_response(self, response):
        """
        Handles a successful response by refreshing the instance fields.
        """
        self.refresh_data(response.json())

    def handle_error_response(self, response):
        """
        Handles an error response that is returned by the server.
        """

        if response.status_code == 400:
            pass
        elif response.status_code == 401:
            pass
        elif response.status_code == 409:
            pass
        elif response.status_code in (500, 503, 504):
            pass

    def refresh_data(self, data):
        """
        Refreshes the instance's attributes with the provided data and
        converts it to the correct type.
        """

        for field in self.resource.fields:
            field.set(data.get(field.name, None))


class Resource:
    """
    A base class for an API resource. This class should be extended for each
    resource endpoint.
    """

    SUPPORTED_METHODS = ()
    PATH = ""
    fields = ()

    def __init__(self):
        self.manager = ResourceManager(self)
        for field in self.fields:
            setattr(self, field.name, field)


class Field:
    """
    A helper class to classify and clean data returned by the API.
    """

    value = None

    def __init__(self, name, clean=str):
        """
        Initialize the Field object with a name and a cleaning function.
        """

        self.name = name
        self.clean = clean

    def __str__(self):
        """
        Return the string representation of the value.
        """
        return str(self.value)

    def __bool__(self):
        """
        Use the value to determine boolean state.
        """
        return self.value is not None

    def set(self, value):
        """
        Set the value of the Field to `value`.
        """
        self.value = value

    @property
    def cleaned_value(self):
        """
        Return the cleaned value of the field (for example, an integer or Date
        object)
        """
        if self.value is not None:
            return self.clean(self.value)


class Job(Resource):
    """
    The API resource corresponding to jobs.
    """

    SUPPORTED_METHODS = ("GET", "POST")
    PATH = "jobs"

    def __init__(self):
        """
        Initialize the Job resource with a set of pre-defined fields.
        """
        self.fields = (
            Field("id", int),
            Field("status"),
            Field("result_url"),
            Field("circuit_url"),
            Field("created_at", dateutil.parser.parse),
            Field("started_at", dateutil.parser.parse),
            Field("finished_at", dateutil.parser.parse),
            Field("running_time", dateutil.parser.parse),
        )
        super().__init__()

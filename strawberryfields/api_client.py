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

"""
APIClient library
================

**Module name:** :mod:`strawberryfields.api_client`

.. currentmodule:: strawberryfields.api_client


This module provides a thin client that communicates with the compute-service API over the HTTP
protocol, based on the requests module. It also provides helper classes to facilitate interacting
with this API via the Resource subclasses, as well as the ResourceManager wrapper around APIClient
that is available for each resource.

A single APIClient instance can be used throughout one's session in the application.

A typical use looks like this:
    .. code-block:: python

        job = Job()
        circuit = '''
            name StateTeleportation
            version 1.0
            target gaussian (shots=1000)

            complex alpha = 1+0.5j
            Coherent(alpha) | 0
            Squeezed(-4) | 1
            Squeezed(4) | 2
            BSgate(pi/4, 0) | (1, 2)
            BSgate(pi/4, 0) | (0, 1)
            MeasureX | 0
            MeasureP | 1
            Xgate(sqrt(2)*q0) | 2
            Zgate(sqrt(2)*q1) | 2
            MeasureHeterodyne() | 2
        '''
        job.manager.create(circuit=circuit})

        job.id  # Returns the job ID that was generated by the server
        job.reload()  # Fetches the latest job data from the server
        job.status  # Prints the status of this job

        job.manager.get(1536)  # Fetches job 1536 from the server and updates the instance

Classes
-------

.. autosummary::
   APIClient
   Resource
   ResourceManager
   Field
   Job
"""


import urllib
import json
import os
import warnings

import dateutil.parser
import requests


def join_path(base_path, path):
    return urllib.parse.urljoin(f"{base_path}/", path)


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

    ALLOWED_HOSTNAMES = ["localhost"]
    DEFAULT_HOSTNAME = "localhost"

    ENV_KEY_PREFIX = "SF_API_"
    ENV_AUTHENTICATION_TOKEN_KEY = f"{ENV_KEY_PREFIX}AUTHENTICATION_TOKEN"
    ENV_API_HOSTNAME_KEY = f"{ENV_KEY_PREFIX}API_HOSTNAME"
    ENV_USE_SSL_KEY = f"{ENV_KEY_PREFIX}USE_SSL"

    def __init__(self, **kwargs):
        """
        Initialize the API client with various parameters.
        """
        # TODO: Load username, password, or authentication token from
        # configuration file

        configuration = {
            "use_ssl": True,
            "hostname": self.DEFAULT_HOSTNAME,
            "authentication_token": None,
        }

        # Try getting everything first from environment variables
        configuration.update(self.get_configuration_from_environment())

        # Override any values that are explicitly passed when initializing client
        configuration.update(kwargs)

        if configuration["hostname"] is None:
            raise ValueError("hostname parameter is missing")

        if configuration["hostname"] not in self.ALLOWED_HOSTNAMES:
            raise ValueError("hostname parameter not in allowed list")

        self.USE_SSL = configuration["use_ssl"]
        if not self.USE_SSL:
            warnings.warn("Connecting insecurely to API server", UserWarning)

        self.HOSTNAME = configuration["hostname"]
        self.BASE_URL = f"{'https' if self.USE_SSL else 'http'}://{self.HOSTNAME}"
        self.AUTHENTICATION_TOKEN = configuration["authentication_token"]
        self.HEADERS = {}

        # TODO: warn if no authentication token

    def get_configuration_from_environment(self):
        """
        Retrieve configuration from environment variables. The variables are defined as follows:
        - SF_API_USE_SSL: True or False
        - SF_API_HOSTNAME: The hostname of the server to connect to
        - SF_API_AUTHENTICATION_TOKEN: The authentication token to use when connecting to the API
        """
        configuration = {
            "authentication_token": os.environ.get(self.ENV_AUTHENTICATION_TOKEN_KEY),
            "hostname": os.environ.get(self.ENV_API_HOSTNAME_KEY),
            "use_ssl": os.environ.get(self.ENV_USE_SSL_KEY),
        }

        return {key: value for key, value in configuration.items() if value is not None}

    def load_configuration_from_file(self):
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
        return join_path(self.BASE_URL, path)

    def get(self, path):
        """
        Sends a GET request to the provided path. Returns a response object.
        """
        try:
            response = requests.get(url=self.join_path(path), headers=self.HEADERS)
        except requests.exceptions.ConnectionError as e:
            response = None
            warnings.warn(f"Could not connect to server ({e})")
        return response

    def post(self, path, payload):
        """
        Converts payload to a JSON string. Sends a POST request to the provided
        path. Returns a response object.
        """
        # TODO: catch any exceptions from dumping JSON
        data = json.dumps(payload)
        try:
            response = requests.post(url=self.join_path(path), headers=self.HEADERS, data=data)
        except requests.exceptions.ConnectionError as e:
            response = None
            warnings.warn(f"Could not connect to server ({e})")
        return response


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
        return join_path(self.resource.PATH, path)

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

    def create(self, **params):
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

    def __init__(self, client=None):
        self.manager = ResourceManager(self, client=client)
        for field in self.fields:
            setattr(self, field.name, field)

    def reload(self):
        """
        A helper method to fetch the latest data from the API.
        """
        if not hasattr(self, "id"):
            raise TypeError("Resource does not have an ID")

        if self.id:
            self.manager.get(self.id)
        else:
            warnings.warn("Could not reload resource data", UserWarning)


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
        return self.clean(self.value) if self.value is not None else None


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
            Field("running_time"),
        )

        self.result = None
        self.circuit = None

        super().__init__()

    def refresh_data(self):
        """
        Refresh the job fields and attach a JobResult and JobCircuit object to the Job instance.
        """

        super().refresh_data()

        if self.result is not None:
            self.result = JobResult(self.id, client=self.manager.client)

        if self.circuit is not None:
            self.circuit = JobCircuit(self.id, client=self.manager.client)


class JobResult(Resource):
    """
    The API resource corresponding to the job result.
    """

    SUPPORTED_METHODS = ("GET",)
    PATH = "jobs/{job_id}/result"

    def __init__(self, job_id):
        """
        Initialize the JobResult resource with a pre-defined field.
        """
        self.fields = (Field("result", json.loads),)

        self.PATH = self.PATH.format(job_id=job_id)
        super().__init__()


class JobCircuit(Resource):
    """
    The API resource corresponding to the job circuit.
    """

    SUPPORTED_METHODS = ("GET",)
    PATH = "jobs/{job_id}/circuit"

    def __init__(self, job_id):
        """
        Initialize the JobCircuit resource with a pre-defined field.
        """
        self.fields = (Field("circuit"),)

        self.PATH = self.PATH.format(job_id=job_id)
        super().__init__()

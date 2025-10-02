# Information System for HIGEO
#### View the running version of the website! [higeo.ru](https://higeo.ru)

This project is a web-based information system for the Department of History of Geology of the Russian Academy of Sciences. It allows users to view, search, and manage information about organizations, people, and documents related to the department.

## Features

- **View Information**: View detailed information about organizations, people, and documents.
- **Search**: Perform searches based on various criteria.
- **Add New Records**: Admins can add new records for organizations, people, and documents.
- **Edit Records**: Admins can edit existing records.
- **Delete Records**: Admins can delete records.

## Installation

1. **Clone the repository**:
    ```sh
    git clone https://github.com/BUSH222/higeo_is.git
    cd higeo_is
    ```

2. **Create a virtual environment**:
    ```sh
    python3 -m venv venv
    source venv/bin/activate
    ```

3. **Install dependencies**:
    ```sh
    pip install -r requirements.txt
    ```

4. **Set up the database**:
    - Ensure PostgreSQL is installed and running.
    - Create a `.env` file with the following content:
        ```env
        DATABASE_NAME = ...
        DATABASE_HOST = ...
        DATABASE_PORT = ...
        DATABASE_USER = ...
        DATABASE_PASSWORD = ...
        GOOGLE_CLIENT_ID = ... (google oauth2 credentials)
        GOOGLE_CLIENT_SECRET = ... (google oauth2 credentials)
        GOOGLE_DISCOVERY_URL = ... (google oauth2 credentials)
        ADMIN_DATA = '{"0": "email1@example.com", "1": "email2@example.com", "2": ...}' (admin users)
        SECRET_KEY = ... (random string)
        ```
    - Initialize the database and fill database with old data, and migrate over the files:
        ```sh
        sh quicksetup.sh
        ```

## Usage

1. **Run the application**:
    ```sh
    cd /path/to/higeo_is
    python3 main.py
    ```

2. **Access the application**:
    Open your web browser and go to `http://localhost:5000`.

> This will run the app in debug mode. Proper hosting is required for normal operation.
## Configuration

- **Environment **Variables:
    - DATABASE_USER: Database username.
    - DATABASE_PASSWORD: Database password.
    - DATABASE_NAME: Database name.
    - DATABASE_HOST: Database host.
    - DATABASE_PORT: Database port.

## Contributing

1. **Fork the repository**.
2. **Create a new branch**:
    ```sh
    git checkout -b feature/your-feature-name
    ```
3. **Make your changes**.
4. **Commit your changes**:
    ```sh
    git commit -m 'Add some feature'
    ```
5. **Push to the branch**:
    ```sh
    git push origin feature/your-feature-name
    ```
6. **Open a pull request**.

## License

This project is licensed under the MIT License.

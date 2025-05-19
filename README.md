# Information System for HIGEO
> README SLIGHTLY OUT OF DATE
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
        DATABASE_USER=your_db_user
        DATABASE_PASSWORD=your_db_password
        DATABASE_NAME=your_db_name
        DATABASE_HOST=localhost
        DATABASE_PORT=5432
        ```
    - Initialize the database and fill database with old data:
        ```sh
        sh quicksetup.sh
        ```

## Usage

1. **Run the application**:
    ```sh
    flask run
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

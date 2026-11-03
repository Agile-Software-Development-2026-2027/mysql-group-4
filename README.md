## MySOL

MySOL is an academic mission management system designed to streamline travel requests and financial reimbursement workflows for university faculty, researchers, and staff, inspired by the system used at the University of Calabria (UniCal). The primary goal of this project is to enhance the platform by integrating AI-powered Optical Character Recognition (OCR) technology into the reimbursement process. By automatically scanning uploaded receipts, tickets, and travel invoices, the system intelligently extracts key data to auto-fill the reimbursement request fields, significantly reducing manual data entry and accelerating administrative processing times.

## How to Run

Prerequisites:
Ensure you have the following installed on your system:
Docker and Docker Compose
Node.js (v18+ recommended) & npm

Running with Docker Compose:
Clone the repository:
git clone <repository-url>
cd mysql-group-4

Start all services:
docker compose up -d --build

Access the application services:
Frontend (Angular): http://localhost:4200
Backend API Docs (FastAPI / Swagger): http://localhost:8000/docs
MinIO Console (Storage): http://localhost:9001

Stop the environment:
docker compose down

If you need to develop or test the frontend standalone outside of Docker:
Navigate to the frontend folder and install dependencies:
cd frontend
npm install

Start the development server:
npm start

Run unit tests:
npm run test

## How we work

- `main` is protected: nobody can push to it, every change goes through a pull request.
- Branches are short-lived (less than a day) and pull requests are small (less than 200 lines).
- A pull request needs the approval of a teammate and a green CI, and must be up to date with
  `main`. It is merged with a squash merge.
- The backlog and the sprints are on the Jira board of the team, not in this repository.
- The title of a pull request starts with the key of the Jira issue it implements:
  `ABC-12 Add the login form`.
- If `main` is red, fixing it comes before anything else.

## CI

`.github/workflows/ci.yml` runs on every pull request. It starts empty and always passes: add
the steps that build and test the project as soon as there is something to test.

test

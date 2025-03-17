-- Insert dummy people
INSERT INTO person (name, surname, patronymic, name_en, surname_en, patronymic_en, birth_date, death_date, birth_place, 
                    death_place, academic_degree, field_of_study, area_of_study, biography, bibliography, photo, comment)
VALUES 
    ('John', 'Doe', 'Michael', 'John', 'Doe', 'Michael', '1975-06-15', NULL, 'New York', NULL, 'PhD', 'Physics', 'Quantum Mechanics', 
     'Biography of John Doe', 'Bibliography of John Doe', 'photo1.jpg', 'No comments'),
    ('Alice', 'Smith', 'Jane', 'Alice', 'Smith', 'Jane', '1980-09-22', NULL, 'London', NULL, 'MSc', 'Computer Science', 'Artificial Intelligence',
     'Biography of Alice Smith', 'Bibliography of Alice Smith', 'photo2.jpg', 'No comments'),
    ('Bob', 'Johnson', NULL, 'Bob', 'Johnson', NULL, '1965-03-10', NULL, 'San Francisco', NULL, 'PhD', 'Mathematics', 'Number Theory',
     'Biography of Bob Johnson', 'Bibliography of Bob Johnson', 'photo3.jpg', 'No comments');

-- Insert dummy organizations
INSERT INTO organization (name, org_type, history, comment)
VALUES 
    ('NASA', 'Space Research', 'Founded in 1958', 'Space research organization'),
    ('MIT', 'Educational', 'Founded in 1861', 'Massachusetts Institute of Technology'),
    ('OpenAI', 'Research Lab', 'Founded in 2015', 'Artificial Intelligence Research Lab');

-- Insert dummy organization memberships
INSERT INTO organization_membership (person_id, organization_id)
VALUES 
    (1, 1), -- John Doe is in NASA
    (2, 2), -- Alice Smith is in MIT
    (3, 3), -- Bob Johnson is in OpenAI
    (1, 3); -- John Doe is also in OpenAI

-- Insert dummy documents
INSERT INTO document (name, doc_type, language, source, year, file, comment)
VALUES 
    ('Quantum Computing Basics', 'Book', 'English', 'Springer', '2020', 'quantum_basics.pdf', 'Introduction to Quantum Computing'),
    ('AI and Ethics', 'Book', 'English', 'Oxford Press', '2022', 'ai_ethics.pdf', 'Discussion on AI Ethics'),
    ('Mathematical Proofs and Theorems', 'Book', 'English', 'Cambridge University Press', '2018', 'math_proofs.pdf', 'Advanced mathematical proofs');

-- Insert dummy document authorship records
INSERT INTO document_authorship (person_id, document_id)
VALUES 
    (1, 1), -- John Doe wrote "Quantum Computing Basics"
    (2, 2), -- Alice Smith wrote "AI and Ethics"
    (3, 3), -- Bob Johnson wrote "Mathematical Proofs and Theorems"
    (2, 1), -- Alice Smith also contributed to "Quantum Computing Basics"
    (3, 2); -- Bob Johnson also contributed to "AI and Ethics"
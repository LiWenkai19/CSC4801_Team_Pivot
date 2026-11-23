import { useEffect, useId, useRef, useState } from 'react'
import './SkillTagPicker.css'
import { useLanguage } from '../../i18n/LanguageContext'
import type { Message } from '../../i18n/LanguageContext'

const suggestions = [
    // 常用技能
    'Python', 'SQL', 'Java', 'JavaScript', 'TypeScript', 'C', 'C++', 'C#', 'Go', 'Rust', 'React', 'Vue',
    'Node.js', 'Django', 'FastAPI', 'Spring Boot', 'PostgreSQL', 'MySQL', 'Redis', 'Git', 'Docker', 'Linux',
    'AWS', 'PyTorch', 'TensorFlow', 'Machine Learning', 'Data Analysis', 'Excel',

    // 编程语言与软件工程
    'HTML', 'CSS', 'Bash', 'PowerShell', 'R', 'MATLAB', 'Julia', 'SAS', 'Stata', 'SPSS', 'Ruby', 'PHP',
    'Swift', 'Kotlin', 'Objective-C', 'Dart', 'Scala', 'Groovy', 'Lua', 'Perl', 'Elixir', 'Erlang', 'Clojure',
    'Haskell', 'F#', 'OCaml', 'Zig', 'Assembly Language', 'WebAssembly', 'Fortran', 'COBOL', 'VBA', 'Delphi',
    'Visual Basic .NET', 'Racket', 'Solidity', 'Verilog', 'SystemVerilog', 'VHDL', 'LaTeX', 'Markdown',
    'Regular Expressions', 'Object-Oriented Programming', 'Functional Programming', 'Concurrent Programming',
    'Multithreading', 'Data Structures', 'Algorithms', 'Design Patterns', 'Code Review',
    'Technical Documentation', 'Technical Debt Management', 'Software Architecture', 'Systems Design',
    'API Design', 'Performance Optimization', 'Debugging', 'Memory Management', 'Version Control',

    // 前端、移动端与游戏开发
    'Angular', 'Svelte', 'Next.js', 'Nuxt', 'SvelteKit', 'Astro', 'SolidJS', 'jQuery', 'React Router',
    'Redux', 'Zustand', 'TanStack Query', 'RxJS', 'Tailwind CSS', 'Bootstrap', 'Sass', 'Material UI',
    'Chakra UI', 'CSS Grid', 'Flexbox', 'Responsive Web Design', 'Web Accessibility', 'WCAG', 'ARIA',
    'Web Components', 'Progressive Web Apps', 'Service Workers', 'Internationalization', 'Localization',
    'Web Performance', 'Webpack', 'Vite', 'Rollup', 'Babel', 'npm', 'Yarn', 'pnpm', 'Storybook',
    'Figma Design Handoff', 'React Native', 'Flutter', 'Android Development', 'iOS Development', 'SwiftUI',
    'UIKit', 'Jetpack Compose', 'Mobile Accessibility', 'App Store Submission', 'Unity', 'Unreal Engine',
    'Godot', 'Game Design', 'Level Design', 'Game Testing', 'Game Physics', 'Computer Graphics', 'OpenGL',
    'Vulkan', 'DirectX', 'WebGL', 'Three.js', 'Shader Programming', 'Graphics Optimization',

    // 后端与系统集成
    'Express.js', 'NestJS', 'Flask', 'Pyramid', 'Ruby on Rails', 'Laravel', 'Symfony', 'ASP.NET Core', '.NET',
    'Spring Framework', 'Hibernate', 'JPA', 'Quarkus', 'Micronaut', 'Gin', 'Actix Web',
    'REST API Development', 'GraphQL', 'gRPC', 'WebSockets', 'Server-Sent Events', 'OpenAPI', 'Swagger',
    'Postman', 'OAuth 2.0', 'OpenID Connect', 'SAML', 'JWT', 'API Gateway Configuration', 'Rate Limiting',
    'Microservices', 'Event-Driven Architecture', 'Distributed Systems', 'Message Queues', 'Apache Kafka',
    'RabbitMQ', 'Apache Pulsar', 'NATS', 'API Integration', 'Systems Integration', 'Caching',
    'Load Balancing', 'Nginx', 'Apache HTTP Server', 'IIS', 'Serverless Development', 'Batch Processing',
    'Background Job Processing',

    // 数据库、数据工程与分析
    'SQLite', 'Oracle Database', 'Microsoft SQL Server', 'MariaDB', 'MongoDB', 'DynamoDB', 'Cassandra',
    'Couchbase', 'Neo4j', 'Elasticsearch', 'OpenSearch', 'Solr', 'ClickHouse', 'DuckDB', 'Amazon Redshift',
    'Google BigQuery', 'Snowflake', 'Databricks', 'Apache Spark', 'PySpark', 'Apache Hadoop', 'Hive',
    'Apache Flink', 'Apache Beam', 'Apache Airflow', 'Prefect', 'Dagster', 'dbt', 'Data Modeling',
    'Database Design', 'Database Administration', 'Database Normalization', 'Database Migration',
    'Schema Management', 'SQL Query Optimization', 'Index Design', 'Transaction Management',
    'Backup and Recovery', 'Replication', 'Data Partitioning', 'Data Warehousing', 'Data Lakes',
    'Data Lakehouse Architecture', 'ETL', 'ELT', 'Data Pipelines', 'Data Integration', 'Data Quality',
    'Data Governance', 'Data Lineage', 'Data Cataloging', 'Metadata Management', 'Master Data Management',
    'Data Visualization', 'Business Intelligence', 'Tableau', 'Power BI', 'DAX', 'Power Query', 'Looker',
    'Qlik Sense', 'Google Sheets', 'Pivot Tables', 'Spreadsheet Modeling', 'Dashboard Design',
    'Reporting Automation', 'Exploratory Data Analysis', 'Statistical Analysis', 'Regression Analysis',
    'Time Series Analysis', 'Forecasting', 'Hypothesis Testing', 'Experimental Design', 'A/B Testing',
    'Survey Analysis', 'Causal Inference',

    // 人工智能与应用统计
    'Deep Learning', 'Natural Language Processing', 'Computer Vision', 'Generative AI', 'Prompt Engineering',
    'Large Language Models', 'Retrieval-Augmented Generation', 'Vector Search', 'Semantic Search',
    'Search Relevance', 'Recommendation Systems', 'Information Retrieval', 'Named Entity Recognition',
    'Text Classification', 'Sentiment Analysis', 'Speech Recognition', 'Audio Signal Processing',
    'Optical Character Recognition', 'Object Detection', 'Image Segmentation', 'Transfer Learning',
    'Model Fine-Tuning', 'Feature Engineering', 'Model Evaluation', 'Model Deployment', 'Model Monitoring',
    'Model Interpretability', 'MLOps', 'Responsible AI', 'Reinforcement Learning', 'Supervised Learning',
    'Unsupervised Learning', 'Anomaly Detection', 'scikit-learn', 'Keras', 'XGBoost', 'LightGBM',
    'Hugging Face Transformers', 'OpenCV', 'NumPy', 'pandas', 'SciPy', 'Matplotlib', 'Seaborn', 'Plotly',
    'Jupyter', 'MLflow', 'ONNX', 'TensorRT', 'Bayesian Statistics', 'Monte Carlo Simulation',
    'Optimization Modeling', 'Operations Research', 'Simulation Modeling',

    // 云平台、运维与技术支持
    'Microsoft Azure', 'Google Cloud Platform', 'Kubernetes', 'Terraform', 'OpenTofu', 'Ansible', 'Puppet',
    'Chef', 'Helm', 'Argo CD', 'Flux CD', 'GitHub Actions', 'GitLab CI/CD', 'Jenkins', 'Azure DevOps',
    'TeamCity', 'CircleCI', 'Bazel', 'Maven', 'Gradle', 'CI/CD', 'Infrastructure as Code',
    'Cloud Architecture', 'Cloud Migration', 'Cloud Cost Optimization', 'FinOps',
    'Site Reliability Engineering', 'Platform Engineering', 'Infrastructure Automation', 'Observability',
    'OpenTelemetry', 'Prometheus', 'Grafana', 'Datadog', 'Splunk', 'Incident Response', 'Root Cause Analysis',
    'On-Call Operations', 'Capacity Planning', 'Disaster Recovery', 'Business Continuity Planning',
    'Service Level Management', 'Windows Server', 'Active Directory', 'Microsoft Entra ID',
    'Microsoft Intune', 'Jamf Pro', 'VMware vSphere', 'Virtualization', 'Virtual Desktop Infrastructure',
    'System Administration', 'Technical Support', 'Help Desk Support', 'Desktop Support', 'ServiceNow',
    'IT Asset Management', 'IT Service Management', 'ITIL', 'Remote Troubleshooting',
    'Network Administration', 'Cisco Networking', 'TCP/IP', 'DNS', 'DHCP', 'HTTP', 'VPN Administration',
    'Firewall Management', 'Network Monitoring', 'Wireless Networking',

    // 软件测试、信息安全与隐私
    'Quality Assurance', 'Test Planning', 'Test Case Design', 'Manual Testing', 'Exploratory Testing',
    'Software Test Automation', 'Unit Testing', 'Integration Testing', 'End-to-End Testing',
    'Regression Testing', 'Smoke Testing', 'Load Testing', 'Usability Testing', 'Cross-Browser Testing',
    'Accessibility Testing', 'User Acceptance Testing', 'Test-Driven Development',
    'Behavior-Driven Development', 'Contract Testing', 'API Testing', 'JUnit', 'pytest', 'Jest', 'Vitest',
    'Selenium', 'Playwright', 'Cypress', 'Appium', 'k6', 'Apache JMeter', 'Cucumber', 'Defect Tracking',
    'Secure Coding', 'Application Security', 'Cloud Security', 'Network Security', 'Endpoint Security',
    'Identity and Access Management', 'Encryption', 'Public Key Infrastructure', 'Key Management',
    'Secrets Management', 'Threat Modeling', 'Security Code Review', 'Vulnerability Management',
    'Security Monitoring', 'Security Incident Management', 'Digital Forensics', 'Security Awareness Training',
    'SIEM', 'Security Auditing', 'Data Loss Prevention', 'Data Privacy', 'Data Protection Impact Assessment',
    'Third-Party Risk Management', 'ISO 27001', 'SOC 2', 'PCI DSS', 'GDPR Compliance',

    // 产品、项目管理与业务分析
    'Product Management', 'Product Strategy', 'Product Discovery', 'Product Roadmapping',
    'Product Operations', 'Product Analytics', 'Product Launch Planning', 'Product Lifecycle Management',
    'Requirements Elicitation', 'Requirements Analysis', 'Requirements Traceability', 'Business Analysis',
    'Business Process Mapping', 'Process Modeling', 'Business Process Reengineering', 'BPMN',
    'Process Improvement', 'Workflow Design', 'User Stories', 'Acceptance Criteria', 'Backlog Management',
    'Prioritization', 'Market Research', 'Competitor Analysis', 'Market Sizing', 'Customer Interviews',
    'Customer Journey Mapping', 'Stakeholder Management', 'Cross-Functional Collaboration',
    'Project Management', 'Program Management', 'Portfolio Management', 'Project Planning',
    'Project Scheduling', 'Scope Management', 'Risk Management', 'Resource Planning', 'Change Management',
    'Agile Delivery', 'Scrum', 'Kanban', 'Sprint Planning', 'Sprint Retrospectives', 'Workshop Facilitation',
    'OKR Planning', 'KPI Development', 'Jira', 'Confluence', 'Asana', 'Trello', 'Notion', 'Microsoft Project',
    'Smartsheet', 'Cost-Benefit Analysis',

    // 体验设计、平面设计与内容制作
    'UX Design', 'UI Design', 'Interaction Design', 'Visual Design', 'Service Design',
    'Information Architecture', 'User Research', 'Design Research', 'Contextual Inquiry',
    'Usability Research', 'Card Sorting', 'Wireframing', 'Prototyping', 'Design Systems', 'Design Thinking',
    'Figma', 'Sketch', 'Adobe XD', 'Graphic Design', 'Brand Identity Design', 'Typography', 'Layout Design',
    'Color Theory', 'Illustration', 'Icon Design', 'Packaging Design', 'Adobe Photoshop', 'Adobe Illustrator',
    'Adobe InDesign', 'Digital Illustration', 'Motion Graphics', 'Adobe After Effects', 'Adobe Premiere Pro',
    'Final Cut Pro', 'DaVinci Resolve', 'Video Editing', 'Videography', 'Photography', 'Photo Retouching',
    'Lighting Design', 'Sound Design', 'Audio Editing', 'Audio Mixing', 'Podcast Production',
    'Broadcast Production', 'Color Grading', 'Storyboarding', 'Screenwriting', 'Script Editing',
    '3D Modeling', '3D Animation', 'Blender', 'Autodesk Maya', 'Cinema 4D', '3D Rendering', 'Compositing',
    'Visual Effects', 'Digital Asset Management', 'Print Production',

    // 销售、市场营销与公关
    'Sales Strategy', 'Lead Generation', 'Sales Prospecting', 'Lead Qualification', 'Cold Calling',
    'Email Outreach', 'Consultative Selling', 'Solution Selling', 'Sales Presentations', 'Sales Negotiation',
    'Sales Forecasting', 'Pipeline Management', 'Account Management', 'Key Account Management',
    'Territory Management', 'Business Development', 'Partnership Development', 'Channel Sales',
    'Retail Sales', 'Sales Enablement', 'Revenue Operations', 'Salesforce', 'HubSpot',
    'Microsoft Dynamics 365', 'CRM Administration', 'Customer Relationship Management', 'Demand Generation',
    'Brand Management', 'Brand Strategy', 'Marketing Strategy', 'Product Marketing',
    'Positioning and Messaging', 'Digital Marketing', 'Search Engine Optimization (SEO)', 'Technical SEO',
    'Search Engine Marketing (SEM)', 'Keyword Research', 'Paid Search', 'Google Ads', 'Paid Social',
    'Meta Ads Manager', 'Email Marketing', 'Marketing Automation', 'Content Marketing', 'Content Strategy',
    'Copywriting', 'Conversion Rate Optimization', 'Google Analytics', 'Google Tag Manager',
    'Marketing Attribution', 'Web Analytics', 'Social Media Management', 'Community Management',
    'Influencer Marketing', 'Event Marketing', 'Public Relations', 'Media Relations', 'Press Release Writing',
    'Crisis Communications', 'Competitive Intelligence', 'Campaign Management', 'Market Segmentation',
    'E-commerce Management', 'Shopify', 'WooCommerce', 'Merchandising', 'Pricing Strategy',

    // 客户服务、零售与行政
    'Customer Service', 'Customer Support', 'Customer Success', 'Customer Onboarding',
    'Client Relationship Management', 'Customer Retention', 'Customer Satisfaction Analysis',
    'Call Center Operations', 'Technical Account Management', 'Zendesk', 'Intercom', 'Freshdesk',
    'Knowledge Base Management', 'Ticket Triage', 'Complaint Resolution', 'De-escalation',
    'Conflict Resolution', 'Escalation Management', 'Telephone Etiquette', 'Active Listening', 'Empathy',
    'Business Writing', 'Presentation Skills', 'Public Speaking', 'Team Leadership', 'People Management',
    'Coaching', 'Mentoring', 'Time Management', 'Meeting Facilitation', 'Meeting Minutes',
    'Calendar Management', 'Executive Support', 'Travel Coordination', 'Office Administration',
    'Office Management', 'Data Entry', 'Records Management', 'Document Control', 'Document Preparation',
    'Microsoft Office', 'Outlook', 'Microsoft Word', 'PowerPoint', 'Microsoft Teams', 'SharePoint',
    'Google Workspace', 'Written Communication', 'Verbal Communication', 'Problem Solving', 'Critical Thinking',
    'Scheduling', 'Appointment Booking', 'Cash Handling', 'Point-of-Sale Operations', 'Inventory Counting',
    'Stock Replenishment', 'Visual Merchandising', 'Loss Prevention', 'Store Operations',

    // 财务、会计与保险
    'Financial Analysis', 'Financial Modeling', 'Financial Planning and Analysis', 'Financial Reporting',
    'Management Accounting', 'Cost Accounting', 'Bookkeeping', 'Accounts Payable', 'Accounts Receivable',
    'General Ledger Accounting', 'Bank Reconciliation', 'Month-End Close', 'Financial Consolidation',
    'Budgeting', 'Variance Analysis', 'Cash Flow Management', 'Treasury Management',
    'Working Capital Management', 'Revenue Recognition', 'Cost Control', 'Tax Preparation', 'Tax Planning',
    'Financial Auditing', 'Internal Audit', 'Internal Controls', 'IFRS Reporting', 'US GAAP Reporting',
    'SOX Compliance', 'Payroll Processing', 'QuickBooks', 'Xero', 'SAP FI', 'Oracle NetSuite',
    'Credit Analysis', 'Credit Risk Assessment', 'Loan Underwriting', 'Investment Analysis',
    'Equity Research', 'Portfolio Analysis', 'Asset Valuation', 'Discounted Cash Flow Analysis',
    'Due Diligence', 'Financial Statement Analysis', 'Investment Portfolio Management',
    'Fixed Income Analysis', 'Insurance Underwriting', 'Claims Processing', 'Claims Assessment',
    'Actuarial Modeling', 'Anti-Money Laundering', 'Know Your Customer', 'Fraud Detection',

    // 人力资源、招聘与培训
    'Talent Acquisition', 'Recruiting', 'Candidate Sourcing', 'Boolean Search', 'Resume Screening',
    'Structured Interviewing', 'Technical Interviewing', 'Employer Branding', 'Campus Recruiting',
    'Applicant Tracking System Administration', 'Workforce Planning', 'Employee Onboarding',
    'Employee Relations', 'Employee Engagement', 'Performance Management', 'Talent Management',
    'Succession Planning', 'Compensation Analysis', 'Benefits Administration', 'Job Evaluation',
    'HR Analytics', 'Human Resource Information Systems', 'Workday', 'SAP SuccessFactors', 'BambooHR',
    'Labor Relations', 'Employee Wellness Program Management', 'Grievance Handling',
    'Training Needs Analysis', 'Training Delivery', 'Learning and Development', 'Organizational Development',
    'Instructional Design', 'Learning Management System Administration', 'E-Learning Development',
    'Assessment Design',

    // 供应链、采购、仓储与物流
    'Supply Chain Management', 'Procurement', 'Strategic Sourcing', 'Vendor Management',
    'Supplier Evaluation', 'Supplier Negotiation', 'Purchase Order Management', 'Category Management',
    'Contract Negotiation', 'Materials Management', 'Materials Requirements Planning', 'Demand Planning',
    'Inventory Management', 'Inventory Forecasting', 'Production Planning', 'Production Scheduling',
    'Sales and Operations Planning', 'Warehouse Management', 'Warehouse Management Systems',
    'Transportation Management', 'Shipment Tracking', 'Freight Forwarding', 'Fleet Management',
    'Route Planning', 'Last-Mile Delivery', 'Dispatch Coordination', 'Order Fulfillment',
    'Returns Management', 'Reverse Logistics', 'Import and Export Documentation', 'Customs Compliance',
    'Cold Chain Logistics', 'Forklift Operation', 'Barcode Scanning', 'SAP MM', 'SAP SD',
    'SAP Warehouse Management', 'Enterprise Resource Planning', 'Logistics Coordination',

    // 制造、质量、设备与工业自动化
    'Lean Manufacturing', 'Six Sigma', 'Kaizen', '5S', 'Value Stream Mapping', 'Continuous Improvement',
    'Statistical Process Control', 'Failure Mode and Effects Analysis', 'Corrective and Preventive Action',
    'Quality Control', 'Quality Inspection', 'Quality Management Systems', 'Supplier Quality Management',
    'ISO 9001', 'Manufacturing Engineering', 'Process Engineering', 'CNC Machining', 'CNC Programming',
    'CNC Milling', 'CNC Turning', 'Blueprint Reading', 'Geometric Dimensioning and Tolerancing', 'Metrology',
    'Calibration', 'Assembly', 'Mechanical Assembly', 'Sheet Metal Fabrication', 'Welding', 'TIG Welding',
    'MIG Welding', 'Machining', 'Industrial Maintenance', 'Preventive Maintenance', 'Predictive Maintenance',
    'Equipment Troubleshooting', 'Injection Molding', 'Additive Manufacturing', '3D Printing', 'Robotics',
    'Industrial Robotics', 'Programmable Logic Controllers', 'Ladder Logic', 'SCADA', 'HMI Configuration',
    'Industrial Networking', 'Pneumatics', 'Hydraulics', 'Instrumentation', 'Control Systems',
    'Process Control', 'Lockout/Tagout',

    // 机械、电子、能源与土木工程
    'Mechanical Design', 'Electrical Design', 'Electronic Circuit Design', 'Analog Circuit Design',
    'Digital Circuit Design', 'Power Electronics', 'PCB Design', 'Schematic Capture', 'Hardware Debugging',
    'Soldering', 'Embedded Systems', 'Firmware Development', 'Real-Time Operating Systems',
    'Microcontroller Programming', 'FPGA Design', 'Signal Processing', 'RF Engineering', 'Antenna Design',
    'LabVIEW', 'Simulink', 'Computer-Aided Design (CAD)', 'SolidWorks', 'AutoCAD', 'Fusion 360',
    'CATIA', 'Creo', 'Siemens NX',
    'Finite Element Analysis', 'Computational Fluid Dynamics', 'ANSYS', 'Thermal Analysis',
    'Structural Analysis', 'Structural Design', 'Mechanical Testing', 'Materials Testing',
    'Product Prototyping', 'Engineering Drawing', 'Tolerance Analysis', 'Reliability Engineering',
    'Systems Engineering', 'Electrical Power Distribution', 'Power Systems Analysis',
    'Renewable Energy Systems', 'Solar PV Design', 'Battery Management Systems', 'Energy Auditing',
    'Civil Engineering Design', 'Geotechnical Analysis', 'Hydrology', 'Traffic Engineering',
    'Stormwater Management', 'Roadway Design', 'Surveying',

    // 建筑、施工与设施维护
    'Architectural Design', 'Building Information Modeling', 'Revit', 'SketchUp', 'Navisworks',
    'Building Code Review', 'Construction Management', 'Construction Estimating', 'Quantity Surveying',
    'Construction Scheduling', 'Site Supervision', 'Subcontractor Management', 'Contract Administration',
    'Construction Safety', 'Site Inspection', 'Building Inspection', 'Cost Estimation', 'Tendering',
    'Blueprint Interpretation', 'Facilities Management', 'Property Maintenance', 'Building Maintenance',
    'Electrical Installation', 'Plumbing', 'HVAC Installation', 'HVAC Maintenance', 'Carpentry', 'Masonry',
    'Drywall Installation', 'Painting and Decorating', 'Roofing', 'Flooring Installation',
    'Concrete Finishing', 'Refrigeration Maintenance', 'Equipment Installation', 'Landscape Design',
    'Site Planning', 'Fire Safety Inspection',

    // 医疗、护理与公共卫生
    'Patient Assessment', 'Patient Education', 'Patient Care', 'Patient Triage', 'Clinical Documentation',
    'Electronic Health Records', 'Vital Signs Monitoring', 'Medication Administration', 'Wound Care',
    'Phlebotomy', 'Specimen Collection', 'Infection Control', 'Sterile Technique', 'Medical Terminology',
    'Medical Coding', 'Medical Billing', 'ICD-10 Coding', 'Healthcare Administration', 'Care Coordination',
    'Case Management', 'Discharge Planning', 'Health Informatics', 'Health Information Management',
    'Occupational Health', 'Patient Scheduling', 'First Aid', 'Cardiopulmonary Resuscitation',
    'Basic Life Support', 'Emergency Medical Care', 'Radiographic Imaging', 'Ultrasound Imaging',
    'Laboratory Diagnostics', 'Physical Therapy', 'Occupational Therapy', 'Nutrition Counseling',
    'Mental Health Counseling', 'Behavioral Health Support', 'Health Promotion', 'Health Education',
    'Community Health Outreach', 'Epidemiology', 'Biostatistics', 'Disease Surveillance',
    'Public Health Program Evaluation', 'Food Safety Inspection',

    // 科研、实验室与法规事务
    'Research Design', 'Literature Review', 'Scientific Writing', 'Technical Editing', 'Grant Writing',
    'Peer Review', 'Qualitative Research', 'Quantitative Research', 'Mixed Methods Research',
    'Research Data Management', 'Laboratory Safety', 'Laboratory Information Management Systems',
    'Good Laboratory Practice', 'Good Manufacturing Practice', 'Good Clinical Practice',
    'Clinical Trial Coordination', 'Clinical Data Management', 'Regulatory Affairs', 'Regulatory Submissions',
    'Standard Operating Procedure Writing', 'Chemical Analysis', 'Analytical Chemistry', 'Chromatography',
    'High-Performance Liquid Chromatography', 'Gas Chromatography', 'Mass Spectrometry', 'Spectroscopy',
    'Microscopy', 'Laboratory Sample Preparation', 'Histology', 'Immunohistochemistry', 'Cell Culture',
    'Bioinformatics', 'Genomic Data Analysis', 'Protein Analysis', 'Scientific Illustration',
    'Laboratory Quality Assurance',

    // 教育、语言与文字编辑
    'Curriculum Development', 'Lesson Planning', 'Classroom Management', 'Differentiated Instruction',
    'Online Teaching', 'Blended Learning', 'Tutoring', 'Academic Advising', 'Formative Assessment',
    'Summative Assessment', 'Rubric Development', 'Special Education', 'Individualized Education Planning',
    'Early Childhood Education', 'Adult Education', 'Literacy Instruction', 'STEM Education',
    'Educational Technology', 'Canvas LMS', 'Moodle', 'Google Classroom',
    'Teaching English as a Second Language', 'Classroom Technology Integration', 'Business English',
    'English', 'Mandarin Chinese', 'Cantonese', 'Spanish', 'French', 'German', 'Japanese', 'Korean',
    'Arabic', 'Portuguese', 'Hindi', 'Italian', 'Vietnamese', 'Russian',
    'Training Material Development', 'Translation', 'Interpretation', 'Localization Testing', 'Transcreation',
    'Transcription', 'Proofreading', 'Copy Editing', 'Fact-Checking', 'Subtitling', 'Closed Captioning',
    'Technical Translation', 'Terminology Management', 'Plain Language Writing',

    // 法律、合规、政策与非营利组织
    'Legal Research', 'Legal Writing', 'Contract Drafting', 'Contract Review', 'Contract Management',
    'Legal Project Management', 'Legal Document Review', 'Litigation Support', 'Electronic Discovery',
    'Intellectual Property Research', 'Trademark Research', 'Patent Searching', 'Corporate Governance',
    'Compliance Management', 'Compliance Auditing', 'Compliance Monitoring', 'Policy Analysis',
    'Policy Development', 'Policy Writing', 'Regulatory Compliance', 'Regulatory Reporting',
    'Ethics and Compliance Training', 'Risk Assessment', 'Enterprise Risk Management',
    'Operational Risk Management', 'Business Impact Analysis', 'Records Retention', 'Public Administration',
    'Community Outreach', 'Volunteer Coordination', 'Fundraising', 'Donor Relations', 'Grant Management',
    'Program Evaluation', 'Impact Measurement', 'Public Consultation', 'Community Engagement',
    'Grant Reporting',

    // 餐饮、酒店、旅游与活动
    'Hospitality Management', 'Hotel Operations', 'Front Desk Operations', 'Hotel Reservations',
    'Concierge Services', 'Guest Relations', 'Guest Services', 'Housekeeping Management',
    'Restaurant Operations', 'Food and Beverage Service', 'Food Preparation', 'Culinary Arts', 'Baking',
    'Pastry Production', 'Menu Planning', 'Recipe Development', 'Food Costing', 'Kitchen Management',
    'Food Safety', 'HACCP', 'Allergen Management', 'Menu Engineering', 'Bartending', 'Barista Skills',
    'Banquet Operations', 'Catering Operations', 'Event Planning', 'Event Coordination', 'Venue Management',
    'Conference Planning', 'Trade Show Management', 'Travel Planning', 'Itinerary Development',
    'Tour Guiding', 'Revenue Management',

    // 农业、环境、安全与地理信息
    'Agronomy', 'Crop Planning', 'Crop Monitoring', 'Soil Sampling', 'Soil Analysis', 'Irrigation Management',
    'Precision Agriculture', 'Integrated Pest Management', 'Greenhouse Management', 'Horticulture',
    'Plant Propagation', 'Livestock Management', 'Animal Husbandry', 'Forestry Management',
    'Environmental Monitoring', 'Environmental Impact Assessment', 'Environmental Compliance',
    'Water Quality Monitoring', 'Waste Management', 'Wastewater Treatment', 'Air Quality Monitoring',
    'Occupational Safety', 'Workplace Safety Training', 'Job Hazard Analysis', 'Safety Auditing',
    'Emergency Preparedness', 'Incident Investigation', 'ISO 14001', 'ISO 45001', 'Carbon Accounting',
    'Greenhouse Gas Reporting', 'Life Cycle Assessment', 'Sustainability Reporting', 'ESG Reporting',
    'ArcGIS', 'QGIS', 'Geographic Information Systems', 'Remote Sensing', 'Spatial Analysis', 'Cartography',
    'GPS Surveying', 'Drone Mapping', 'Conservation Planning',

    // 公共服务、社会工作与其他专业服务
    'Social Work Assessment', 'Crisis Intervention', 'Family Support', 'Advocacy', 'Safeguarding',
    'Youth Development', 'Community Program Management', 'Benefits Eligibility Assessment',
    'Library Cataloging', 'Library Collection Development', 'Archival Processing', 'Digital Preservation',
    'Museum Collections Management', 'Exhibition Design', 'Security Operations',
    'Access Control Administration', 'Emergency Dispatch', 'Fire Prevention',
    'Search and Rescue Coordination', 'Road Safety Management', 'Vehicle Inspection',
    'Automotive Diagnostics', 'Automotive Repair', 'Collision Repair', 'Tire Service', 'Small Engine Repair',
    'Marine Navigation', 'Aviation Maintenance', 'Ground Handling', 'Cargo Handling', 'Driver Training',
    'Fitness Instruction', 'Personal Training', 'Sports Coaching', 'Sports Performance Analysis',
    'Event Security', 'Textile Design', 'Pattern Making', 'Garment Construction', 'Sewing', 'Tailoring',
    'Cosmetology', 'Hair Styling', 'Makeup Artistry', 'Pet Grooming',
]
const normalize = (value: string) => value.trim().toLowerCase()

type Props = { value: string[]; onChange: (skills: string[]) => void }

/** 首次填写与编辑共用：搜索预设技能，也可添加自己的标签。 */
function SkillTagPicker({ value, onChange }: Props) {
    const { t } = useLanguage()
    const id = useId()
    const input = useRef<HTMLInputElement>(null)
    const [query, setQuery] = useState('')
    const [notice, setNotice] = useState<Message | ''>('')
    const validationMessage = t('skills.uncommitted')
    const options = suggestions.filter(skill => normalize(skill).includes(normalize(query)) && !value.includes(normalize(skill)))

    useEffect(() => {
        const field = input.current
        field?.setCustomValidity(field.value.trim() ? validationMessage : '')
    }, [validationMessage])

    function add(text: string) {
        const name = normalize(text)
        if (!name) return
        if (!value.includes(name)) onChange([...value, name])
        setNotice({ key: value.includes(name) ? 'skills.alreadySelected' : 'skills.added', values: { skill: name } })
        setQuery('')
        input.current?.setCustomValidity('')
        input.current?.focus()
    }

    return <fieldset className="skill-picker">
        <legend>{t('skills.optional')}</legend>
        <ul aria-label={t('skills.selected')}>
            {value.map(skill => <li key={skill}>{skill} <button type="button" aria-label={t('skills.removeOne', { skill })} onClick={() => onChange(value.filter(item => item !== skill))}>{t('skills.remove')}</button></li>)}
        </ul>
        <label htmlFor={id}>{t('skills.search')}</label>
        <div className="skill-input">
            <input ref={input} id={id} value={query} autoComplete="off" aria-describedby={`${id}-help`} onChange={event => {
                const next = event.target.value
                setQuery(next)
                event.target.setCustomValidity(next.trim() ? validationMessage : '')
            }} onKeyDown={event => {
                if (event.key === 'Enter' && !event.nativeEvent.isComposing && event.keyCode !== 229) {
                    event.preventDefault()
                    add(query)
                }
            }} />
            <button type="button" disabled={!query.trim()} onClick={() => add(query)}>{t('skills.add')}</button>
        </div>
        <p id={`${id}-help`}>{t('skills.help')}</p>
        {query.trim() && <ul aria-label={t('skills.suggestions')}>
            {options.slice(0, 8).map(skill => <li key={skill}><button type="button" onClick={() => add(skill)}>{skill}</button></li>)}
            {!options.length && <li>{t('skills.noMatches')}</li>}
        </ul>}
        <p role="status">{notice && t(notice)}</p>
    </fieldset>
}

export default SkillTagPicker

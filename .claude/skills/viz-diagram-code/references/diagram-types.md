# Diagram Types Reference

Comprehensive syntax and patterns for all supported Mermaid diagram types.
Use these as templates when generating diagrams.

---

## Flowchart (most common for tutorials)

The workhorse diagram type. Use for pipelines, processes, decision trees, and
any sequential or branching logic.

### Linear pipeline

```mermaid
%%{init: {'theme': 'neutral'}}%%
flowchart TB
    subgraph "Data Preprocessing"
        A[Raw Data] --> B{Quality Check}
        B -->|Pass| C[Normalization]
        B -->|Fail| D[Data Cleaning]
        D --> B
    end
    C --> E[Feature Extraction]
    E --> F[Model Training]

    classDef input fill:#f9d5e5,stroke:#333
    classDef process fill:#d5e8f9,stroke:#333
    classDef decision fill:#e8f5e9,stroke:#333
    class A input
    class C,D,E,F process
    class B decision
```

### Multi-stage pipeline (Pretraining to Alignment style)

```mermaid
%%{init: {'theme': 'neutral'}}%%
flowchart LR
    A[Unlabeled<br/>Corpus] --> B[Pretraining]
    B --> C[Base Model]
    C --> D[Supervised<br/>Finetuning]
    D --> E[SFT Model]
    E --> F[RLHF /<br/>DPO]
    F --> G[Aligned<br/>Model]

    classDef data fill:#f9d5e5,stroke:#333,color:#333
    classDef train fill:#d5e8f9,stroke:#333,color:#333
    classDef model fill:#e8f5e9,stroke:#333,color:#333
    class A data
    class B,D,F train
    class C,E,G model
```

### Decision tree with Yes/No branches

```mermaid
%%{init: {'theme': 'neutral'}}%%
flowchart TB
    A{Is sample size<br/>greater than 30?} -->|Yes| B{Normal<br/>distribution?}
    A -->|No| C[Non-parametric test]
    B -->|Yes| D{Two groups<br/>or more?}
    B -->|No| C
    D -->|Two| E[t-test]
    D -->|More| F[ANOVA]

    classDef decision fill:#fff3cd,stroke:#333,color:#333
    classDef result fill:#d5e8f9,stroke:#333,color:#333
    class A,B,D decision
    class C,E,F result
```

### Multi-path flow with parallel branches

```mermaid
%%{init: {'theme': 'neutral'}}%%
flowchart TB
    A[Input Data] --> B[Validation]
    B --> C{Data Type}
    C -->|Tabular| D[Pandas Pipeline]
    C -->|Image| E[CV Pipeline]
    C -->|Text| F[NLP Pipeline]
    D --> G[Results]
    E --> G
    F --> G

    classDef start fill:#f9d5e5,stroke:#333
    classDef branch fill:#d5e8f9,stroke:#333
    classDef end_ fill:#e8f5e9,stroke:#333
    class A,B start
    class D,E,F branch
    class G end_
```

### Nested subgraphs for grouped components

```mermaid
%%{init: {'theme': 'neutral'}}%%
flowchart TB
    subgraph "Experiment Setup"
        subgraph "Treatment Group"
            T1[Sample A<br/>n=50]
            T2[Sample B<br/>n=50]
        end
        subgraph "Control Group"
            C1[Sample C<br/>n=50]
            C2[Sample D<br/>n=50]
        end
    end
    T1 & T2 --> M[Measure Outcome]
    C1 & C2 --> M
    M --> S[Statistical Analysis]
    S --> R[Report Results]
```

### Node shapes reference

```
[Rectangle]     — standard process
(Rounded)       — soft step
{Diamond}       — decision
([Stadium])     — terminal / start-end
[(Cylinder)]    — database / storage
[[Subroutine]]  — subprocess
((Circle))      — connector
>Asymmetric]    — input
{Hexagon}       — preparation (use {{Hexagon}})
```

---

## Sequence Diagram (protocols and interactions)

Best for: API calls, experimental protocols, message-passing systems.

```mermaid
sequenceDiagram
    participant U as User
    participant S as Server
    participant DB as Database

    U->>S: POST /analyze
    activate S
    S->>DB: Query dataset
    activate DB
    DB-->>S: Results (n=1000)
    deactivate DB
    S->>S: Run statistical tests
    S-->>U: 200 OK + report.json
    deactivate S
```

### With loops and conditionals

```mermaid
sequenceDiagram
    participant R as Researcher
    participant L as Lab System
    participant A as Analysis Pipeline

    R->>L: Submit sample batch
    loop Each sample in batch
        L->>L: Run assay
        alt Quality pass
            L->>A: Send results
        else Quality fail
            L->>R: Flag for re-run
        end
    end
    A->>R: Aggregated report
```

### Notes and highlighting

```mermaid
sequenceDiagram
    participant C as Client
    participant A as Auth
    participant API as API

    C->>A: Login request
    Note over A: Validate credentials
    A-->>C: JWT token
    C->>API: Request + JWT
    Note over API: Verify token
    API-->>C: Protected resource
    Note right of C: Cache response<br/>for 5 minutes
```

---

## Architecture Diagram (system overviews)

Use flowchart with subgraphs to create layered architecture views.

```mermaid
%%{init: {'theme': 'neutral'}}%%
flowchart TB
    subgraph "Frontend"
        A[Web App]
        B[Mobile App]
    end
    subgraph "Backend"
        C[API Gateway]
        D[Auth Service]
        E[Data Service]
    end
    subgraph "Storage"
        F[(PostgreSQL)]
        G[(Redis Cache)]
    end
    A & B --> C
    C --> D & E
    E --> F & G

    classDef frontend fill:#d5e8f9,stroke:#333,color:#333
    classDef backend fill:#e8f5e9,stroke:#333,color:#333
    classDef storage fill:#fff3cd,stroke:#333,color:#333
    class A,B frontend
    class C,D,E backend
    class F,G storage
```

### ML system architecture

```mermaid
%%{init: {'theme': 'neutral'}}%%
flowchart TB
    subgraph "Data Layer"
        S3[(Object Store)]
        DW[(Data Warehouse)]
    end
    subgraph "Training"
        FE[Feature<br/>Engineering]
        TR[Model<br/>Training]
        EV[Evaluation]
    end
    subgraph "Serving"
        REG[Model<br/>Registry]
        INF[Inference<br/>API]
        MON[Monitoring]
    end

    S3 --> FE
    DW --> FE
    FE --> TR --> EV
    EV -->|Promote| REG
    REG --> INF
    INF --> MON
    MON -->|Drift detected| TR

    classDef data fill:#f9d5e5,stroke:#333,color:#333
    classDef train fill:#d5e8f9,stroke:#333,color:#333
    classDef serve fill:#e8f5e9,stroke:#333,color:#333
    class S3,DW data
    class FE,TR,EV train
    class REG,INF,MON serve
```

---

## Mind Map (concept exploration)

```mermaid
mindmap
  root((Machine Learning))
    Supervised
      Classification
        Logistic Regression
        SVM
        Random Forest
      Regression
        Linear Regression
        Gradient Boosting
    Unsupervised
      Clustering
        K-Means
        DBSCAN
      Dimensionality Reduction
        PCA
        t-SNE
        UMAP
    Reinforcement
      Policy Gradient
        PPO
        A3C
      Q-Learning
        DQN
        Double DQN
```

Mind maps auto-style based on depth level. Keep labels short (1-3 words).

---

## Timeline (historical or process views)

```mermaid
timeline
    title History of Large Language Models
    2017 : Transformer architecture
         : Attention Is All You Need
    2018 : BERT (Google)
         : GPT-1 (OpenAI)
    2019 : GPT-2
         : XLNet
    2020 : GPT-3 (175B params)
    2022 : ChatGPT
         : Chinchilla scaling laws
    2023 : GPT-4
         : Claude 2
         : Llama 2
    2024 : Claude 3
         : Gemini
         : Llama 3
```

Keep timeline entries concise. Use multiple entries per year with `:` prefix.

---

## Class Diagram (data models and ontologies)

```mermaid
classDiagram
    class Experiment {
        +String id
        +String title
        +Date startDate
        +Status status
        +addSample(Sample)
        +analyze() Results
    }
    class Sample {
        +String sampleId
        +String type
        +Float concentration
        +validate() bool
    }
    class Results {
        +Float pValue
        +Float effectSize
        +String interpretation
        +export(format) File
    }

    Experiment "1" --> "*" Sample : contains
    Experiment "1" --> "1" Results : produces
```

Useful for scientific data structures, database schemas, and taxonomies.

---

## State Diagram (experimental protocols)

```mermaid
stateDiagram-v2
    [*] --> SamplePrep
    SamplePrep --> QualityCheck
    QualityCheck --> Sequencing : Pass
    QualityCheck --> SamplePrep : Fail
    Sequencing --> DataProcessing
    DataProcessing --> Analysis
    Analysis --> Review
    Review --> Published : Approved
    Review --> Analysis : Revisions needed
    Published --> [*]
```

Good for showing experimental workflows with branching and loops.

---

## Comparison Layout (side-by-side)

Use flowchart LR with parallel subgraphs for comparing two approaches.

```mermaid
%%{init: {'theme': 'neutral'}}%%
flowchart LR
    subgraph "Supervised Learning"
        direction TB
        A1[Labeled Data] --> B1[Model]
        B1 --> C1[Loss Function]
        C1 --> D1[Backpropagation]
        D1 --> B1
    end
    subgraph "Reinforcement Learning"
        direction TB
        A2[Environment] --> B2[Agent]
        B2 --> C2[Action]
        C2 --> A2
        A2 --> D2[Reward]
        D2 --> B2
    end

    classDef sup fill:#d5e8f9,stroke:#333,color:#333
    classDef rl fill:#e8f5e9,stroke:#333,color:#333
    class A1,B1,C1,D1 sup
    class A2,B2,C2,D2 rl
```

### Three-way comparison

For three approaches, stack three subgraphs vertically (TB) or use a grid layout.

---

## Syntax Quick Reference

| Feature | Syntax |
|---------|--------|
| Theme init | `%%{init: {'theme': 'neutral'}}%%` |
| Direction | `flowchart TB` / `LR` / `BT` / `RL` |
| Arrow | `A --> B` |
| Arrow with label | `A -->&#124;label&#124; B` |
| Dotted arrow | `A -.-> B` |
| Thick arrow | `A ==> B` |
| Subgraph | `subgraph "Title"` ... `end` |
| Class def | `classDef name fill:#hex,stroke:#hex,color:#hex` |
| Apply class | `class A,B className` or `A:::className` |
| Line break in text | `A[Line 1<br/>Line 2]` |
| Link multiple | `A & B --> C` |
| Comment | `%% This is a comment` |

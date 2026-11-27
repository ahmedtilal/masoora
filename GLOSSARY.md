# Masoora

Masoora defines and runs data pipelines. Its vocabulary describes the work in a pipeline, the data it passes between steps, and the configuration shared across a run.

## Language

### Pipelines and steps

**Pipeline**:
A reusable definition of **Steps** and their data dependencies.

**Pipeline run**:
One execution of a **Pipeline** with a **Pipeline context** and a **Data catalog**. A run can be limited to a **Target**.

**Pipeline context**:
The shared, read-only configuration available to every **Step** in a **Pipeline run**.

**Step**:
A declared unit of work in a **Pipeline**, with **Inputs** and **Outputs** according to its kind.

**Read step**:
A **Step** that brings a **Dataset** into the **Data catalog** from a source. It has one **Output** and takes no catalog **Inputs**.

**Transform step**:
A **Step** that computes a **Dataset** from the **Pipeline context** and any declared **Inputs**. It has one **Output**.

**Write step**:
A **Step** that sends one or more **Datasets** from the **Data catalog** to a destination. It has no catalog **Output**.

### Data flow

**Dataset**:
A data value stored at a **Catalog key**. It can be a table, a scalar, or a reference to data stored elsewhere.

**Data catalog**:
The collection of **Datasets** available by **Catalog key** during a **Pipeline run**.

**Catalog key**:
The name of a slot in the **Data catalog** that can hold a **Dataset**.

**Input**:
A **Catalog key** declared by a **Step** for a **Dataset** it consumes.

**Output**:
A **Catalog key** declared by a **Step** for the **Dataset** it produces.

**Seed**:
A **Catalog key** declared for a **Dataset** the caller supplies before the **Pipeline run**.

**Target**:
An **Output** selected for a **Pipeline run**. The run includes the **Step** that produces it and the upstream **Steps** it depends on.

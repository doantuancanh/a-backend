┌───────────────────────┐
│        Users           │
├───────────────────────┤
│ user_id (PK)          │
│ name                  │
│ email                 │
│ telegram_id           │
│ role                  │  (admin/member)
└───────────────────────┘

┌───────────────────────┐
│  PotentialProjects     │
├───────────────────────┤
│ potential_id (PK)     │
│ name                  │
│ chain                 │
│ source                │
│ discovered_at         │
└───────────────────────┘

┌───────────────────────┐
│       Projects         │
├───────────────────────┤
│ project_id (PK)       │
│ name                  │
│ chain                 │
│ source                │
│ status                │  (active/inactive)
│ created_at            │
│ created_by (FK→Users) │
└───────────────────────┘

┌───────────────────────┐
│        Tasks           │
├───────────────────────┤
│ task_id (PK)          │
│ project_id (FK→Projects) │
│ title                 │
│ description           │
│ deadline              │
│ status (pending/done) │
│ link (URL)            │
│ created_at            │
└───────────────────────┘

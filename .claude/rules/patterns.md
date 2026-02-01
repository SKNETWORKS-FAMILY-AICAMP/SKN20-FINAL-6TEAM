# Code Patterns (Bizi Project)

## Python / FastAPI Patterns

### Pydantic Schema Pattern
```python
from pydantic import BaseModel, Field, ConfigDict

# Request schema (no Config needed)
class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., pattern=r"^[A-Z]\d{3}$")

# Response schema (with ORM support)
class ItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
```

### SQLAlchemy 2.0 Pattern
```python
from sqlalchemy import select
from sqlalchemy.orm import Session

# Query (2.0 style - use select(), not query())
stmt = select(User).where(User.email == email)
user = db.execute(stmt).scalar_one_or_none()

# Eager loading
stmt = select(User).options(selectinload(User.companies))
```

### FastAPI Router Pattern
```python
router = APIRouter(prefix="/items", tags=["items"])

def get_service(db: Session = Depends(get_db)) -> ItemService:
    return ItemService(db)

@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(
    item_id: int,
    service: ItemService = Depends(get_service),
    current_user: User = Depends(get_current_user),
):
    item = service.get_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item
```

### Service Layer Pattern
```python
class ItemService:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, item_id: int) -> Item | None:
        return self.db.get(Item, item_id)

    def create(self, data: ItemCreate, user_id: int) -> Item:
        item = Item(**data.model_dump(), user_id=user_id)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item
```

## React / TypeScript Patterns

### Zustand Store Pattern
```typescript
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface StoreState {
    items: Item[];
    addItem: (item: Item) => void;
    reset: () => void;
}

export const useItemStore = create<StoreState>()(
    persist(
        (set) => ({
            items: [],
            addItem: (item) => set((s) => ({ items: [...s.items, item] })),
            reset: () => set({ items: [] }),
        }),
        { name: 'item-store' }
    )
);
```

### TanStack Query Hook Pattern
```typescript
export const useItemQuery = (id: number) =>
    useQuery({
        queryKey: ['item', id],
        queryFn: () => api.get(`/items/${id}`).then((r) => r.data),
        enabled: !!id,
    });

export const useCreateItemMutation = () =>
    useMutation({
        mutationFn: (data: ItemCreate) => api.post('/items', data),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['items'] }),
    });
```

### Component Props Pattern
```typescript
interface Props {
    item: Item;
    onEdit: (id: number) => void;
    disabled?: boolean;
}

const ItemCard: React.FC<Props> = ({ item, onEdit, disabled = false }) => {
    return (/* ... */);
};
```

## LangChain / RAG Patterns

### Agent Pattern
```python
class DomainAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="domain", collection_name="domain_db")

    async def process(self, query: str, context: dict) -> str:
        docs = await self.retrieve(query, k=5)
        prompt = self.build_prompt(query, docs, context)
        return (await self.llm.ainvoke(prompt)).content
```

### Prompt Template Pattern
```python
# All prompts in rag/utils/prompts.py
DOMAIN_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "Role description\n\nContext:\n{context}"),
    ("human", "{query}"),
])
```

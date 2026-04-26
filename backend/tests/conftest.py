"""Fixtures compartilhadas de teste.

- `db_session`: Session SQLAlchemy com rollback automático por teste.
  Isola cada teste via connection + transaction + rollback — nada é persistido.
- `client`: TestClient FastAPI com dependency_override de `get_db_session`,
  garantindo que o endpoint usa a mesma session do teste.
- Factories (`city_factory`, `category_factory`, `store_factory`): criam
  registros mínimos válidos pra testes de repositório/endpoint.
"""

import uuid
from collections.abc import Generator
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.models.user import User

from app.api.deps import get_db_session, get_sms_provider
from app.core.rate_limit import limiter
from app.db.session import get_engine
from app.main import app
from app.services.sms.mock import MockSMSProvider
from tests.utils.phone import generate_valid_phone_e164
from tests.utils.tax_id import generate_valid_cnpj


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> Generator[None, None, None]:
    """Reseta o rate limiter (slowapi/Redis) antes de cada teste.

    Sem reset, contagens persistidas em Redis vazariam entre testes —
    o 11º POST /auth/request-otp em qualquer teste falharia 429
    (limit 10/hora por IP, e TestClient sempre usa mesmo "IP").

    Testes específicos de rate limit acumulam contagens DENTRO do teste
    (reset só ocorre entre testes, não dentro).
    """
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Session de DB com rollback automático por teste.

    Usa connection + transaction explícita + rollback no final
    pra garantir isolamento entre testes. Requer que migrations
    já tenham rodado (alembic upgrade head) no banco de teste.
    """
    connection = get_engine().connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def mock_sms_provider() -> MockSMSProvider:
    """MockSMSProvider pronto pra testes (APP_ENV=local, aceita valid phones).

    Endpoint de auth injeta via Depends(get_sms_provider) — fixture `client`
    aplica override com essa instância. Testes que precisam variantes
    (ex: simular SMSSendError) podem usar MAGIC_FAILURE_PHONE direto no
    payload (pattern ADR-025) sem trocar o provider.
    """
    return MockSMSProvider(app_env="local")


@pytest.fixture
def client(
    db_session: Session,
    mock_sms_provider: MockSMSProvider,
) -> Generator[TestClient, None, None]:
    """TestClient com override de get_db_session e get_sms_provider.

    Garante que o endpoint usa a mesma session que o teste (rollback
    automático) e provider mockado. app.dependency_overrides.clear()
    no teardown cobre ambos os overrides.
    """

    def _override_get_db_session() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = _override_get_db_session
    app.dependency_overrides[get_sms_provider] = lambda: mock_sms_provider
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def city_factory(db_session: Session) -> Any:
    """Cria uma City válida (MG) pra testes."""
    from app.models.city import City

    def _create(**overrides: Any) -> City:
        suffix = uuid.uuid4().hex[:6]
        defaults: dict[str, Any] = {
            "id": uuid.uuid4(),
            "name": f"Cidade Teste {suffix}",
            "state": "MG",
            "slug": f"cidade-teste-{suffix}",
            "is_active": True,
        }
        defaults.update(overrides)
        city = City(**defaults)
        db_session.add(city)
        db_session.flush()
        return city

    return _create


@pytest.fixture
def category_factory(db_session: Session) -> Any:
    """Cria uma Category pra testes."""
    from app.models.category import Category

    def _create(**overrides: Any) -> Category:
        suffix = uuid.uuid4().hex[:6]
        defaults: dict[str, Any] = {
            "id": uuid.uuid4(),
            "name": f"Categoria {suffix}",
            "slug": f"cat-{suffix}",
            "is_active": True,
        }
        defaults.update(overrides)
        cat = Category(**defaults)
        db_session.add(cat)
        db_session.flush()
        return cat

    return _create


@pytest.fixture
def product_factory(db_session: Session, store_factory: Any) -> Any:
    """Cria um Product pra testes. Status default ACTIVE."""
    from app.domain.enums import ProductStatus
    from app.models.product import Product

    def _create(**overrides: Any) -> Product:
        suffix = uuid.uuid4().hex[:6]
        store = overrides.pop("store", None) or store_factory()
        defaults: dict[str, Any] = {
            "id": uuid.uuid4(),
            "store_id": store.id,
            "name": f"Produto {suffix}",
            "status": ProductStatus.ACTIVE,
        }
        defaults.update(overrides)
        product = Product(**defaults)
        db_session.add(product)
        db_session.flush()
        return product

    return _create


@pytest.fixture
def product_variation_factory(db_session: Session) -> Any:
    """Cria uma ProductVariation (exige product explícito)."""
    from app.models.product_variation import ProductVariation

    def _create(product: Any, **overrides: Any) -> ProductVariation:
        suffix = uuid.uuid4().hex[:6]
        defaults: dict[str, Any] = {
            "id": uuid.uuid4(),
            "product_id": product.id,
            "name": f"Variação {suffix}",
            "price_cents": 1000,
            "sort_order": 0,
        }
        defaults.update(overrides)
        v = ProductVariation(**defaults)
        db_session.add(v)
        db_session.flush()
        return v

    return _create


@pytest.fixture
def addon_group_factory(db_session: Session, store_factory: Any) -> Any:
    """Cria um AddonGroup pra testes. Tipo default SINGLE."""
    from app.domain.enums import AddonGroupType
    from app.models.addon_group import AddonGroup

    def _create(**overrides: Any) -> AddonGroup:
        suffix = uuid.uuid4().hex[:6]
        store = overrides.pop("store", None) or store_factory()
        defaults: dict[str, Any] = {
            "id": uuid.uuid4(),
            "store_id": store.id,
            "name": f"Grupo {suffix}",
            "type": AddonGroupType.SINGLE.value,
            "min_selections": 0,
            "max_selections": 1,
            "sort_order": 0,
        }
        defaults.update(overrides)
        g = AddonGroup(**defaults)
        db_session.add(g)
        db_session.flush()
        return g

    return _create


@pytest.fixture
def addon_factory(db_session: Session) -> Any:
    """Cria um Addon (exige group explícito)."""
    from app.models.addon import Addon

    def _create(group: Any, **overrides: Any) -> Addon:
        suffix = uuid.uuid4().hex[:6]
        defaults: dict[str, Any] = {
            "id": uuid.uuid4(),
            "group_id": group.id,
            "name": f"Adicional {suffix}",
            "price_cents": 500,
            "is_available": True,
            "sort_order": 0,
        }
        defaults.update(overrides)
        a = Addon(**defaults)
        db_session.add(a)
        db_session.flush()
        return a

    return _create


@pytest.fixture
def product_addon_group_factory(db_session: Session) -> Any:
    """Cria a junção M:N ProductAddonGroup (exige product e group explícitos)."""
    from app.models.product_addon_group import ProductAddonGroup

    def _create(product: Any, group: Any, **overrides: Any) -> ProductAddonGroup:
        defaults: dict[str, Any] = {
            "id": uuid.uuid4(),
            "product_id": product.id,
            "group_id": group.id,
            "sort_order": 0,
        }
        defaults.update(overrides)
        pag = ProductAddonGroup(**defaults)
        db_session.add(pag)
        db_session.flush()
        return pag

    return _create


@pytest.fixture
def store_factory(
    db_session: Session,
    city_factory: Any,
    category_factory: Any,
) -> Any:
    """Cria uma Store pra testes. Status default APPROVED.

    Cobre todos os NOT NULLs reais do Store (legal_name/trade_name/tax_id/
    tax_id_type/slug/street/number/neighborhood/zip_code/status/FKs).
    tax_id gerado por generate_valid_cnpj pra satisfazer UNIQUE + @validates.
    """
    from app.domain.enums import StoreStatus, TaxIdType
    from app.models.store import Store

    def _create(**overrides: Any) -> Store:
        suffix = uuid.uuid4().hex[:6]
        city = overrides.pop("city", None) or city_factory()
        category = overrides.pop("category", None) or category_factory()

        defaults: dict[str, Any] = {
            "id": uuid.uuid4(),
            "legal_name": f"Teste Store LTDA {suffix}",
            "trade_name": f"Store {suffix}",
            "tax_id": generate_valid_cnpj(),
            "tax_id_type": TaxIdType.CNPJ,
            "slug": f"store-{suffix}",
            "street": "Rua Teste",
            "number": "123",
            "neighborhood": "Centro",
            "zip_code": "35855000",
            "status": StoreStatus.APPROVED,
            "city_id": city.id,
            "category_id": category.id,
            # phone NOT NULL adicionado em ADR-026 CP1a HIGH #1.
            "phone": generate_valid_phone_e164(),
        }
        defaults.update(overrides)
        store = Store(**defaults)
        db_session.add(store)
        db_session.flush()
        return store

    return _create


@pytest.fixture
def user_factory(db_session: Session) -> Any:
    """Cria um User pra testes. Phone E.164 válido gerado por sorteio."""
    from app.models.user import User

    def _create(**overrides: Any) -> User:
        defaults: dict[str, Any] = {
            "id": uuid.uuid4(),
            "phone": generate_valid_phone_e164(),
        }
        defaults.update(overrides)
        user = User(**defaults)
        db_session.add(user)
        db_session.flush()
        return user

    return _create


@pytest.fixture
def customer_factory(db_session: Session, user_factory: Any) -> Any:
    """Cria um Customer pra testes (CP1 do Ciclo Customer, ADR-027).

    Cria User automaticamente se `user` não for passado nos overrides.
    Garante `customer.phone == user.phone` por default (ADR-027 dec. 6 —
    phone do Customer vem do User logado).
    """
    from app.models.customer import Customer

    def _create(**overrides: Any) -> Customer:
        # Aceita 'user' como atalho — pega phone + user_id automaticamente.
        user = overrides.pop("user", None) or user_factory()
        defaults: dict[str, Any] = {
            "id": uuid.uuid4(),
            "user_id": user.id,
            "phone": user.phone,  # ADR-027 dec. 6
            "name": "Cliente Teste",
        }
        defaults.update(overrides)
        customer = Customer(**defaults)
        db_session.add(customer)
        db_session.flush()
        return customer

    return _create


@pytest.fixture
def otp_code_factory(db_session: Session) -> Any:
    """Cria um OtpCode pra testes. expires_at default now + 10 min (ADR-025)."""
    from datetime import UTC, datetime, timedelta

    from app.models.otp_code import OtpCode

    def _create(**overrides: Any) -> OtpCode:
        defaults: dict[str, Any] = {
            "id": uuid.uuid4(),
            "phone": generate_valid_phone_e164(),
            "code_hash": "0" * 64,
            "expires_at": datetime.now(UTC) + timedelta(minutes=10),
            "attempts": 0,
        }
        defaults.update(overrides)
        otp = OtpCode(**defaults)
        db_session.add(otp)
        db_session.flush()
        return otp

    return _create


@pytest.fixture
def authenticated_user(db_session: Session) -> "User":
    """User persistido no banco para uso em testes autenticados (CP4).

    Phone gerado via generate_valid_phone_e164 pra evitar conflito UNIQUE
    com testes de auth real (request-otp/verify-otp). Usa db_session.flush()
    em vez de commit() pra preservar rollback automático no teardown
    (lição CP1 — fixture compartilhada não fecha transação real).
    """
    from app.models.user import User

    user = User(phone=generate_valid_phone_e164())
    db_session.add(user)
    db_session.flush()
    db_session.refresh(user)
    return user


@pytest.fixture
def authenticated_client(
    client: TestClient,
    authenticated_user: "User",
) -> TestClient:
    """TestClient com header Authorization: Bearer <jwt-real> embutido (CP4).

    Gera JWT real via create_access_token (CP3a) — sem mocking.
    Útil pra testar endpoints protegidos end-to-end. Herda overrides de
    get_db_session e get_sms_provider da fixture client base.
    """
    from app.services.auth.jwt import create_access_token

    token = create_access_token(
        user_id=authenticated_user.id,
        phone=authenticated_user.phone,
    )
    client.headers["Authorization"] = f"Bearer {token}"
    return client

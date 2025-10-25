from fastapi import APIRouter, Depends, HTTPException, status

from infrastructure.context import RequestContextBundle
from routers.dependencies import get_request_context_bundle, get_admin_context_bundle
from schemas import (
    ProductCreateRequest,
    ProductResponse,
    UserCreateRequest,
    UserResponse,
)
from services.user import UserProductService

router = APIRouter()


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreateRequest,
    context_bundle: RequestContextBundle = Depends(get_admin_context_bundle),
) -> UserResponse:
    service = UserProductService(context_bundle.db, context_bundle.scope)
    await service.upsert_user(external_id=payload.user_id, name=payload.name)
    user, products = await service.get_user_with_products(payload.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User creation failed")
    return UserResponse(
        user_id=user.external_id,
        name=user.name,
        products=[
            ProductResponse(
                product_id=product.external_id,
                project_id=product.project_id,
                name=product.name,
            )
            for product in products
        ],
    )


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    context_bundle: RequestContextBundle = Depends(get_admin_context_bundle),
) -> UserResponse:
    service = UserProductService(context_bundle.db, context_bundle.scope)
    user, products = await service.get_user_with_products(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse(
        user_id=user.external_id,
        name=user.name,
        products=[
            ProductResponse(
                product_id=product.external_id,
                project_id=product.project_id,
                name=product.name,
            )
            for product in products
        ],
    )


@router.post(
    "/users/{user_id}/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_product(
    user_id: str,
    payload: ProductCreateRequest,
    context_bundle: RequestContextBundle = Depends(get_admin_context_bundle),
) -> ProductResponse:
    service = UserProductService(context_bundle.db, context_bundle.scope)
    product = await service.add_product_to_user(
        external_id=user_id,
        product_external_id=payload.product_id,
        product_name=payload.name,
    )
    return ProductResponse(
        product_id=product.external_id,
        project_id=product.project_id,
        name=product.name,
    )

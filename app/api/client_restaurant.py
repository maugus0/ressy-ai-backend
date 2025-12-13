from fastapi import APIRouter, Body, Depends, status

from app.api.restaurants import RestaurantResponse, UpdateRestaurantRequest, get_restaurant_service
from app.middleware.auth_middleware import get_current_restaurant_user
from app.utils.payload_validator import validate_payload

router = APIRouter(
    prefix="/api/v1/client",
    tags=["Restaurants"],
    dependencies=[Depends(get_current_restaurant_user)],
)


@router.get(
    "/restaurant",
    summary="Get restaurant (Client)",
    response_model=RestaurantResponse,
    description="Return the authenticated restaurant details.",
    response_description="Restaurant details scoped to the authenticated restaurant.",
    openapi_extra={
        "responses": {
            200: {
                "description": "Restaurant retrieved",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 10,
                            "name": "Ressy Test Kitchen",
                            "phone_number": "+15551234567",
                            "opening_time": "09:00:00",
                            "closing_time": "22:00:00",
                        }
                    }
                },
            }
        }
    },
)
async def get_restaurant(
    service=Depends(get_restaurant_service),
    claims: dict = Depends(get_current_restaurant_user),
):
    restaurant_id = int(claims["restaurant_id"])
    return service.get_restaurant(restaurant_id)


@router.put(
    "/restaurant",
    status_code=status.HTTP_200_OK,
    summary="Update restaurant (Client)",
    description="Update the authenticated restaurant. All fields are optional; server-side validation still applies.",
    response_model=RestaurantResponse,
    response_description="Updated restaurant details.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": UpdateRestaurantRequest.model_json_schema(),
                    "example": {"name": "Updated Restaurant", "forward_minutes": 30},
                }
            },
        },
        "responses": {
            200: {
                "description": "Restaurant updated",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 10,
                            "name": "Updated Restaurant",
                            "phone_number": "+15551234567",
                            "forward_minutes": 30,
                            "opening_time": "09:00:00",
                            "closing_time": "22:00:00",
                        }
                    }
                },
            }
        },
    },
)
async def update_restaurant(
    payload: dict = Body(..., description="Restaurant fields to update"),
    service=Depends(get_restaurant_service),
    claims: dict = Depends(get_current_restaurant_user),
):
    restaurant_id = int(claims["restaurant_id"])
    data = validate_payload(UpdateRestaurantRequest, payload)
    return service.update_restaurant(restaurant_id, data.model_dump(exclude_unset=True))

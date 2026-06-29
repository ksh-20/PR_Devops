from fastapi.responses import JSONResponse

def handle_error_response(response, resource_name="Resource"):
    if response.status_code == 401:
        return JSONResponse(
            status_code=401,
            content={
                "error": "Unauthorized",
                "message": "Invalid PAT token or insufficient permissions"
            }
        )

    if response.status_code == 404:
        return JSONResponse(
            status_code=404,
            content={
                "error": "Not Found",
                "message": f"{resource_name} not found"
            }
        )

    return JSONResponse(
        status_code=response.status_code,
        content={
            "error": "Request Failed",
            "message": response.text
        }
    )
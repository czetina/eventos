def company_context(request):
    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        return {"current_company": user.company}
    return {"current_company": None}

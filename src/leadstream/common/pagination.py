from rest_framework.pagination import CursorPagination, PageNumberPagination


class StandardPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


class DiscoveryCursorPagination(CursorPagination):
    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 1_000
    ordering = ("rank", "id")

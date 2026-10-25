namespace Readarr.Api.V1.Books
{
    public class BookManualAddResource
    {
        public int AuthorId { get; set; }
        public string Title { get; set; }
        public int? Year { get; set; }
        public string Language { get; set; }
        public string Asin { get; set; }
        public string Isbn13 { get; set; }
        public string Publisher { get; set; }
        public int? PageCount { get; set; }
        public string Overview { get; set; }
        public bool Monitored { get; set; } = true;
        public bool SearchForNewBook { get; set; }
    }
}

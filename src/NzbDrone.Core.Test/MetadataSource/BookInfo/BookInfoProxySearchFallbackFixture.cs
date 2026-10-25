using System.Collections.Generic;
using System.Net;
using FluentAssertions;
using Moq;
using NUnit.Framework;
using NzbDrone.Common.Http;
using NzbDrone.Core.Http;
using NzbDrone.Core.MetadataSource;
using NzbDrone.Core.MetadataSource.BookInfo;
using NzbDrone.Core.MetadataSource.Goodreads;
using NzbDrone.Core.Test.Framework;

namespace NzbDrone.Core.Test.MetadataSource.BookInfo
{
    [TestFixture]
    public class BookInfoProxySearchFallbackFixture : CoreTest<BookInfoProxy>
    {
        private const string WorkJson = @"{
            ""ForeignId"": 2,
            ""Title"": ""Test Book"",
            ""Url"": ""https://www.goodreads.com/work/2"",
            ""Genres"": [],
            ""RelatedWorks"": [],
            ""Books"": [
                {
                    ""ForeignId"": 20,
                    ""Title"": ""Test Book"",
                    ""Format"": ""Kindle Edition"",
                    ""IsEbook"": true,
                    ""NumPages"": 100,
                    ""RatingCount"": 10,
                    ""AverageRating"": 4.0,
                    ""Url"": ""https://www.goodreads.com/book/show/20"",
                    ""ReleaseDate"": ""2020-01-01T00:00:00Z"",
                    ""Contributors"": [{ ""ForeignId"": 2, ""Role"": ""Author"" }]
                }
            ],
            ""Authors"": [
                {
                    ""ForeignId"": 2,
                    ""Name"": ""Test Author"",
                    ""Url"": ""https://www.goodreads.com/author/show/2"",
                    ""Works"": []
                }
            ],
            ""Series"": []
        }";

        [SetUp]
        public void Setup()
        {
            Mocker.GetMock<IGoodreadsSearchProxy>()
                .Setup(x => x.Search(It.IsAny<string>()))
                .Returns(new List<SearchJsonResource>
                {
                    new SearchJsonResource { BookId = 10, WorkId = 2 },
                    new SearchJsonResource { BookId = 11, WorkId = 3 }
                });

            Mocker.GetMock<IMetadataRequestBuilder>()
                .Setup(x => x.GetRequestBuilder())
                .Returns(new HttpRequestBuilder("http://localhost/{route}").CreateFactory());

            var bulkRequest = new HttpRequest("http://localhost/book/bulk");
            var bulkResponse = new HttpResponse(
                bulkRequest,
                new HttpHeader(),
                "404 page not found",
                HttpStatusCode.NotFound);

            Mocker.GetMock<IHttpClient>()
                .Setup(x => x.Post<BulkBookResource>(It.IsAny<HttpRequest>()))
                .Throws(new HttpException(bulkRequest, bulkResponse));

            Mocker.GetMock<IHttpClient>()
                .Setup(x => x.Get(It.IsAny<HttpRequest>()))
                .Returns<HttpRequest>(request =>
                {
                    if (request.Url.ToString().Contains("/work/3"))
                    {
                        return new HttpResponse(
                            request,
                            new HttpHeader(),
                            "not found",
                            HttpStatusCode.NotFound);
                    }

                    return new HttpResponse(
                        request,
                        new HttpHeader { ContentType = "application/json" },
                        WorkJson);
                });
        }

        [Test]
        public void should_fall_back_to_work_lookup_when_bulk_search_fails()
        {
            var result = Subject.SearchForNewBook("test book", null, false);

            result.Should().ContainSingle();
            result[0].ForeignBookId.Should().Be("2");
            result[0].Title.Should().Be("Test Book");
        }

        [Test]
        public void should_fall_back_to_author_lookup_when_bulk_search_fails()
        {
            Mocker.GetMock<IGoodreadsSearchProxy>()
                .Setup(x => x.Search(It.IsAny<string>()))
                .Returns(new List<SearchJsonResource>
                {
                    new SearchJsonResource
                    {
                        BookId = 10,
                        WorkId = 2,
                        Author = new AuthorJsonResource { Id = 2, Name = "Test Author" }
                    },
                    new SearchJsonResource
                    {
                        BookId = 11,
                        WorkId = 3,
                        Author = new AuthorJsonResource { Id = 2, Name = "Test Author" }
                    }
                });

            var authorJson = @"{
                ""ForeignId"": 2,
                ""Name"": ""Test Author"",
                ""Url"": ""https://www.goodreads.com/author/show/2"",
                ""Works"": [" + WorkJson + @"],
                ""Series"": []
            }";

            Mocker.GetMock<ICachedHttpResponseService>()
                .Setup(x => x.Get(It.IsAny<HttpRequest>(), It.IsAny<bool>(), It.IsAny<System.TimeSpan>()))
                .Returns<HttpRequest, bool, System.TimeSpan>((request, useCache, ttl) =>
                    new HttpResponse(
                        request,
                        new HttpHeader { ContentType = "application/json" },
                        authorJson));

            var result = Subject.SearchForNewBook("test book", null, false);

            result.Should().ContainSingle();
            result[0].ForeignBookId.Should().Be("2");
        }
    }
}

using FluentAssertions;
using NUnit.Framework;
using NzbDrone.Core.MediaFiles.BookImport.Identification;
using NzbDrone.Core.MediaFiles.BookImport.Specifications;
using NzbDrone.Core.Parser.Model;
using NzbDrone.Core.Test.Framework;

namespace NzbDrone.Core.Test.MediaFiles.BookImport.Specifications
{
    [TestFixture]
    public class CloseBookMatchSpecificationFixture : CoreTest<CloseBookMatchSpecification>
    {
        private LocalEdition _localEdition;

        [SetUp]
        public void Setup()
        {
            // The default distance carries a full book_id penalty, i.e. a normalized distance of 1.0
            _localEdition = new LocalEdition
            {
                NewDownload = true
            };
        }

        private void GivenCloseMatch()
        {
            _localEdition.Distance = new Distance();
            _localEdition.Distance.Add("book_id", 0.0);
        }

        [Test]
        public void should_accept_forced_match_even_if_not_close()
        {
            _localEdition.Forced = true;

            Subject.IsSatisfiedBy(_localEdition, null).Accepted.Should().BeTrue();
        }

        [Test]
        public void should_reject_unforced_match_if_not_close()
        {
            Subject.IsSatisfiedBy(_localEdition, null).Accepted.Should().BeFalse();
        }

        [Test]
        public void should_accept_unforced_match_if_close()
        {
            GivenCloseMatch();

            Subject.IsSatisfiedBy(_localEdition, null).Accepted.Should().BeTrue();
        }

        [Test]
        public void should_accept_forced_existing_library_match()
        {
            _localEdition.Forced = true;
            _localEdition.NewDownload = false;

            Subject.IsSatisfiedBy(_localEdition, null).Accepted.Should().BeTrue();
        }
    }
}

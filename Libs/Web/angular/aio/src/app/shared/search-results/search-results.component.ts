import { Component, EventEmitter, Input, OnChanges, Output } from '@angular/core';
import { SearchResult, SearchResults, SearchArea } from 'app/search/interfaces';

enum SearchState {
  InProgress = 'in-progress',
  ResultsFound = 'results-found',
  NoResultsFound = 'no-results-found'
}

/**
 * A component to display search results in groups
 */
@Component({
  selector: 'aio-search-results',
  templateUrl: './search-results.component.html',
})
export class SearchResultsComponent implements OnChanges {

  /**
   * The results to display
   */
  @Input()
  searchResults: SearchResults | null = null;

  /**
   * Emitted when the user selects a search result
   */
  @Output()
  resultSelected = new EventEmitter<SearchResult>();

  readonly defaultArea = 'other';
  searchState: SearchState = SearchState.InProgress;
  readonly topLevelFolders = ['api', 'cli', 'guide', 'start', 'tutorial'];
  searchAreas: SearchArea[] = [];

  ngOnChanges() {
    if (this.searchResults === null) {
      this.searchState = SearchState.InProgress;
    } else if (this.searchResults.results.length) {
      this.searchState = SearchState.ResultsFound;
    } else {
      this.searchState = SearchState.NoResultsFound;
    }
    this.searchAreas = this.processSearchResults(this.searchResults);
  }

  onResultSelected(page: SearchResult, event: MouseEvent) {
    // Emit a `resultSelected` event if the result is to be displayed on this page.
    if (event.button === 0 && !event.ctrlKey && !event.metaKey) {
      this.resultSelected.emit(page);
    }
  }

  // Map the search results into groups by area
  private processSearchResults(search: SearchResults | null) {
    if (!search) {
      return [];
    }
    const searchAreaMap: { [key: string]: SearchResult[] } = {};
    search.results.forEach(result => {
      if (!result.title) { return; } // bad data; should fix
      const areaName = this.computeAreaName(result) || this.defaultArea;
      const area = searchAreaMap[areaName] = searchAreaMap[areaName] || [];
      area.push(result);
    });
    const keys = Object.keys(searchAreaMap).sort((l, r) => l > r ? 1 : -1);
    return keys.map(name => {
      const {priorityPages, pages, deprecated} = splitPages(searchAreaMap[name]);
      return {
        name,
        priorityPages,
        pages: pages.concat(deprecated),
      };
    });
  }

  // Split the search result path and use the top level folder, if there is one, as the area name.
  private computeAreaName(result: SearchResult) {
    if (this.topLevelFolders.indexOf(result.path) !== -1) {
      return result.path;
    }
    const [areaName, rest] = result.path.split('/', 2);
    return rest && areaName;
  }
}

function splitPages(allPages: SearchResult[]) {
  const priorityPages: SearchResult[] = [];
  const pages: SearchResult[] = [];
  const deprecated: SearchResult[] = [];
  allPages.forEach(page => {
    if (page.deprecated) {
      deprecated.push(page);
    } else if (priorityPages.length < 5) {
      priorityPages.push(page);
    } else {
      pages.push(page);
    }
  });
  while (priorityPages.length < 5 && pages.length) {
    priorityPages.push(pages.shift()!);
  }
  while (priorityPages.length < 5 && deprecated.length) {
    priorityPages.push(deprecated.shift()!);
  }
  pages.sort(compareResults);

  return { priorityPages, pages, deprecated };
}

function compareResults(l: SearchResult, r: SearchResult) {
  return l.title.toUpperCase() > r.title.toUpperCase() ? 1 : -1;
}

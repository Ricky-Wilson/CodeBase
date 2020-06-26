import { browser, element, by, promise, ElementFinder, ExpectedConditions } from 'protractor';

const githubRegex = /https:\/\/github.com\/angular\/angular\//;

export class SitePage {

  links = element.all(by.css('md-toolbar a'));
  homeLink = element(by.css('a.home'));
  docsMenuLink = element(by.cssContainingText('aio-top-menu a', 'Docs'));
  sidenav = element(by.css('mat-sidenav'));
  docViewer = element(by.css('aio-doc-viewer'));
  codeExample = element.all(by.css('aio-doc-viewer pre > code'));
  ghLinks = this.docViewer
    .all(by.css('a'))
    .filter((a: ElementFinder) => a.getAttribute('href').then(href => githubRegex.test(href)));

  static setWindowWidth(newWidth: number) {
    const win = browser.driver.manage().window();
    return win.getSize().then(oldSize => win.setSize(newWidth, oldSize.height));
  }

  getNavItem(pattern: RegExp) {
    return element.all(by.css('aio-nav-item .vertical-menu-item'))
                  .filter(elementFinder => elementFinder.getText().then(text => pattern.test(text)))
                  .first();
  }
  getNavItemHeadings(parent: ElementFinder, level: number) {
    const targetSelector = `aio-nav-item .vertical-menu-item.heading.level-${level}`;
    return parent.all(by.css(targetSelector));
  }
  getNavItemHeadingChildren(heading: ElementFinder, level: number) {
    const targetSelector = `.heading-children.level-${level}`;
    const script = `return arguments[0].parentNode.querySelector('${targetSelector}');`;
    return element(() => browser.executeScript(script, heading));
  }
  getTopMenuLink(path: string) { return element(by.css(`aio-top-menu a[href="${path}"]`)); }

  ga() { return browser.executeScript('return window["ga"].q') as promise.Promise<any[][]>; }
  locationPath() { return browser.executeScript('return document.location.pathname') as promise.Promise<string>; }

  navigateTo(pageUrl: string) {
    // Navigate to the page, disable animations, and wait for Angular.
    return browser.get('/' + pageUrl)
        .then(() => browser.executeScript('document.body.classList.add(\'no-animations\')'))
        .then(() => browser.waitForAngular());
  }

  getDocViewerText() {
    return this.docViewer.getText();
  }

  getInnerHtml(elementFinder: ElementFinder) {
    // `getInnerHtml` was removed from webDriver and this is the workaround.
    // See https://github.com/angular/protractor/blob/master/CHANGELOG.md#breaking-changes
    return browser.executeScript('return arguments[0].innerHTML;', elementFinder);
  }

  getScrollTop() {
    return browser.executeScript('return window.pageYOffset');
  }

  scrollTo(y: 'top' | 'bottom' | number) {
    const yExpr = (y === 'top') ? '0' : (y === 'bottom') ? 'document.body.scrollHeight' : y;

    return browser.executeScript(`
      window.scrollTo(0, ${yExpr});
      window.dispatchEvent(new Event('scroll'));
    `);
  }

  click(elementFinder: ElementFinder) {
    return elementFinder.click().then(() => browser.waitForAngular());
  }

  enterSearch(query: string) {
    const input = element(by.css('.search-container input[type=search]'));
    input.clear();
    input.sendKeys(query);
  }

  getSearchResults() {
    const results = element.all(by.css('.search-results li'));
    browser.wait(ExpectedConditions.presenceOf(results.first()), 8000);
    return results.map(link => link && link.getText());
  }

  getApiSearchResults() {
    const results = element.all(by.css('aio-api-list .api-item'));
    browser.wait(ExpectedConditions.presenceOf(results.first()), 2000);
    return results.map(elem => elem && elem.getText());
  }

  clickDropdownItem(dropdown: ElementFinder, itemName: string){
    dropdown.element(by.css('.form-select-button')).click();
    const menuItem = dropdown.element(by.cssContainingText('.form-select-dropdown li', itemName));
    menuItem.click();
  }
}

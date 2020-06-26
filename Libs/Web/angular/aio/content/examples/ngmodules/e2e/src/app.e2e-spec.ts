'use strict'; // necessary for es6 output in node

import { browser, element, by } from 'protractor';

describe('NgModule-example', function () {

  // helpers
  const lightgray = 'rgba(239, 238, 237, 1)';
  const white = 'rgba(0, 0, 0, 0)';

  function getCommonsSectionStruct() {
    const buttons = element.all(by.css('nav a'));

    return {
      title: element.all(by.tagName('h1')).get(0),
      subtitle: element.all(by.css('app-root p i')).get(0),
      contactButton: buttons.get(0),
      itemButton: buttons.get(1),
      customersButton: buttons.get(2)
    };
  }

  function getContactSectionStruct() {
    const buttons = element.all(by.css('app-contact form button'));

    return {
      header: element.all(by.css('app-contact h2')).get(0),
      popupMessage: element.all(by.css('app-contact div')).get(0),
      contactNameHeader: element.all(by.css('app-contact form h3')).get(0),
      input: element.all(by.css('app-contact form input')).get(0),
      validationError: element.all(by.css('app-contact form .alert')).get(0),
      saveButton: buttons.get(0), // can't be tested
      nextContactButton: buttons.get(1),
      newContactButton: buttons.get(2)
    };
  }

  function getItemSectionStruct() {
    return {
      title: element.all(by.css('ng-component h3')).get(0),
      items: element.all(by.css('ng-component a')),
      itemId: element.all(by.css('ng-component div')).get(0),
      listLink: element.all(by.css('ng-component a')).get(0),
    };
  }

  function getCustomersSectionStruct() {
    return {
      header: element.all(by.css('ng-component h2')).get(0),
      title: element.all(by.css('ng-component h3')).get(0),
      items: element.all(by.css('ng-component a')),
      itemId: element.all(by.css('ng-component ng-component div div')).get(0),
      itemInput: element.all(by.css('ng-component ng-component input')).get(0),
      listLink: element.all(by.css('ng-component ng-component a')).get(0),
    };
  }

  // tests
  function appTitleTests(color: string, name?: string) {
    return function() {
      it('should have a gray header', function() {
        const commons = getCommonsSectionStruct();
        expect(commons.title.getCssValue('backgroundColor')).toBe(color);
      });

      it('should welcome us', function () {
        const commons = getCommonsSectionStruct();
        expect(commons.subtitle.getText()).toBe('Welcome, ' + (name ||  'Miss Marple'));
      });
    };
  }

  function contactTests(color: string, name?: string) {
    return function() {
      it('shows the contact\'s owner', function() {
        const contacts = getContactSectionStruct();
        expect(contacts.header.getText()).toBe((name ||  'Miss Marple') + '\'s Contacts');
      });

      it('can cycle between contacts', function () {
        const contacts = getContactSectionStruct();
        const nextButton = contacts.nextContactButton;
        expect(contacts.contactNameHeader.getText()).toBe('Awesome Yasha');
        expect(contacts.contactNameHeader.getCssValue('backgroundColor')).toBe(color);
        nextButton.click().then(function () {
          expect(contacts.contactNameHeader.getText()).toBe('Awesome Iulia');
          return nextButton.click();
        }).then(function () {
          expect(contacts.contactNameHeader.getText()).toBe('Awesome Karina');
        });
      });

      it('can create a new contact', function () {
        const contacts = getContactSectionStruct();
        const newContactButton = contacts.newContactButton;
        const nextButton = contacts.nextContactButton;
        const input = contacts.input;
        const saveButton = contacts.saveButton;

        newContactButton.click().then(function () {
          input.click();
          nextButton.click()
          expect(contacts.validationError.getText()).toBe('Name is required.');
          input.click();
          contacts.input.sendKeys('Watson');
          saveButton.click()
          expect(contacts.contactNameHeader.getText()).toBe('Awesome Watson');

        });
      });
    };
  }

  describe('index.html', function () {
    beforeEach(function () {
      browser.get('');
    });

    describe('app-title', appTitleTests(white, 'Miss Marple'));

    describe('contact', contactTests(lightgray, 'Miss Marple'));

    describe('item center', function () {
      beforeEach(function () {
        getCommonsSectionStruct().itemButton.click();
      });

      it('shows a list of items', function () {
        const item = getItemSectionStruct();
        expect(item.title.getText()).toBe('Items List');
        expect(item.items.count()).toBe(4);
        expect(item.items.get(0).getText()).toBe('1 - Sticky notes');
      });

      it('can navigate to one item details', function () {
        const item = getItemSectionStruct();
        item.items.get(0).click().then(function() {
          expect(item.itemId.getText()).toBe('Item id: 1');
          return item.listLink.click();
        }).then(function () {
          // We are back to the list
          expect(item.items.count()).toBe(4);
        });
      });
    });

    describe('customers', function () {
      beforeEach(function () {
        getCommonsSectionStruct().customersButton.click();
      });

      it('shows a list of customers', function() {
        const customers = getCustomersSectionStruct();
        expect(customers.header.getText()).toBe('Customers of Miss Marple times 2');
        expect(customers.title.getText()).toBe('Customer List');
        expect(customers.items.count()).toBe(6);
        expect(customers.items.get(0).getText()).toBe('11 - Julian');
      });

      it('can navigate and edit one customer details', function () {
        const customers = getCustomersSectionStruct();
        customers.items.get(0).click().then(function () {
          expect(customers.itemId.getText()).toBe('Id: 11');
          customers.itemInput.sendKeys(' try');
          return customers.listLink.click();
        }).then(function () {
          // We are back to the list
          expect(customers.items.count()).toBe(6);
          expect(customers.items.get(0).getText()).toBe('11 - Julian try');
        });
      });
    });
  });

});

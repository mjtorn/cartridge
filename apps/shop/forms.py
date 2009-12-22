
from copy import copy
from datetime import datetime
from django import forms
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.utils.datastructures import SortedDict
from django.contrib.formtools.wizard import FormWizard
from shop.models import Order, ProductVariation


CARD_TYPE_CHOICES = ("Mastercard", "Visa", "Diners", "Amex")
CARD_TYPE_CHOICES = zip(CARD_TYPE_CHOICES, CARD_TYPE_CHOICES)
CARD_MONTHS = ["%02d" % i for i in range(1, 13)]
CARD_MONTHS = zip(CARD_MONTHS, CARD_MONTHS)
		

def get_add_cart_form(product):
	"""
	return the add to cart form dynamically adding the options to it using the 
	variations of the given product
	"""

	class AddCartForm(forms.Form):
		"""
		add to cart form for product
		"""

		quantity = forms.IntegerField(min_value=1)
	
		def clean(self):
			"""
			strip out the quantity from the data leaving only the options
			and if there are any use them to validation the variation
			"""
			options = self.cleaned_data.copy()
			options.pop("quantity")
			if options:
				try:
					product.variations.get(**options)
				except ProductVariation.DoesNotExist:
					raise forms.ValidationError("Selected options are unavailable")
			return self.cleaned_data

	# list of option names
	option_names = [field.name for field in ProductVariation.option_fields()]
	# list of variation sequences containing only option values
	option_values = product.variations.values_list(*option_names)
	# unzip the option value sequences and zip them up with the option names
	option_fields = dict(zip(option_names, zip(*option_values)))
	# create the actual form fields using distinct option values as choices
	for name, values in option_fields.items():
		values = set(values)
		option_fields[name] = forms.ChoiceField(choices=zip(values, values))
	# create the new form type to return
	return type("AddCartForm", (AddCartForm,), option_fields)

class OrderForm(forms.ModelForm):
	"""
	model form for order with billing and shipping details - step 1 of checkout
	"""

	class Meta:
		model = Order
		fields = (Order.billing_field_names() + Order.shipping_field_names() + 
			["additional_instructions"])
			
	def _fieldset(self, prefix):
		"""
		return a subset of fields by making a copy of itself containing only 
		the fields with the given prefix, storing the given prefix each time 
		it's called and when finally called with the prefix "other", returning 
		a copy with all the fields that have not yet been returned
		"""
		
		if not hasattr(self, "_fields_done"):
			self._fields_done = {}
		fieldset = copy(self)
		fieldset.fields = SortedDict([field for field in self.fields.items() if 
			(prefix != "other" and field[0].startswith(prefix)) or 
			(prefix == "other" and field[0] not in self._fields_done.keys())])
		self._fields_done.update(fieldset.fields)
		return fieldset
	
	def __getattr__(self, name):
		"""
		dynamic fieldset caller
		"""
		
		if name.startswith("fieldset_"):
			return self._fieldset(name.split("fieldset_", 1)[1])
		raise AttributeError, name
		

class ExpiryYearField(forms.ChoiceField):
	"""
	choice field for credit card expiry with 20 years from now as choices
	"""

	def __init__(self, *args, **kwargs):
		year = datetime.now().year
		years = range(year, year + 21)
		kwargs["choices"] = zip(years, years)
		super(ExpiryYearField, self).__init__(*args, **kwargs)
		
class PaymentForm(forms.Form):
	"""
	credit card details form - step 2 of checkout
	"""
	
	card_name = forms.CharField()
	card_type = forms.ChoiceField(choices=CARD_TYPE_CHOICES)
	card_number = forms.CharField()
	card_expiry_month = forms.ChoiceField(choices=CARD_MONTHS)
	card_expiry_year = ExpiryYearField()
	card_ccv = forms.CharField()

class CheckoutWizard(FormWizard):
	"""
	combine the 2 checkout step forms into a form wizard
	"""

	def get_template(self, step):
		return "shop/%s.html" % ("billing_shipping", "payment")[int(step)]

	def done(self, request, form_list):
		"""
		payment integreation goes here
		"""
		
		return HttpResponseRedirect(reverse("shop_complete"))

checkout_wizard = CheckoutWizard([OrderForm, PaymentForm])

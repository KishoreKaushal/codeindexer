; --- scope captures ---

; namespace_identifier — NOT plain identifier!
(namespace_definition
  name: (namespace_identifier) @scope.ns.name)
  @scope.ns

; type_identifier — NOT plain identifier!
(class_specifier
  name: (type_identifier) @scope.class.name)
  @scope.class

(struct_specifier
  name: (type_identifier) @scope.struct.name)
  @scope.struct

; !name = "node does NOT have a name: field"
; Named ns already matched above.
(namespace_definition
  !name) @scope.ns.anon

; [...]  =  alternation — match either type
; field_identifier = in-class member names
; identifier = free function / outer scope names
(function_definition
  declarator: (function_declarator
    declarator: 
    [
      (identifier)       @name.plain
      (field_identifier) @name.plain
    ]
    parameters: (parameter_list) @params)
  body: (compound_statement) @body)
  @fn.plain

; math::Subber::sub, Greeter::Greeter
(function_definition
  declarator: (function_declarator
    declarator: (qualified_identifier) @name.qual
    parameters: (parameter_list) @params)
  body: (compound_statement)) @fn.qualified

; ~Resource
(function_definition
  declarator: (function_declarator
    declarator: (destructor_name) @name.dtor
    parameters: (parameter_list) @params)
  body: (compound_statement)) @fn.dtor

; friend ostream& operator<<(...)
; T& return wraps fn_declarator in reference_declarator!
(function_definition
  declarator: (reference_declarator
    (function_declarator
      declarator: (operator_name) @name.refop
      parameters: (parameter_list) @params))
  body: (compound_statement)) @fn.refop


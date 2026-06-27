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

; operator (by-value return)
(function_definition
  declarator: (function_declarator
    declarator: (operator_name) @name.operator
    parameters: (parameter_list) @params)
  body: (compound_statement)) @fn.operator

; friend ostream& operator<<(...)
; T& return wraps fn_declarator in reference_declarator!
(function_definition
  declarator: (reference_declarator
    (function_declarator
      declarator: (operator_name) @name.refop
      parameters: (parameter_list) @params))
  body: (compound_statement)) @fn.refop

; Methods declared (no body) inside struct/class:
;   struct { void foo_x(); } TestStructType;
;   class Subber { public: int sub(int x); };
; These are field_declaration nodes, NOT function_definition.
(field_declaration
  declarator: (function_declarator
    declarator: (field_identifier) @name.field_decl
    parameters: (parameter_list) @params.field_decl))
  @fn.field_decl

; Capture wrapper nodes — byte ranges only
(template_declaration) @mod.template
(friend_declaration)   @mod.friend

; Forward decl lives under `declaration` (no body!)
; Not `function_definition` — those require compound_statement.
; Only qualified ones: int math::Adder::sum(int x);
(declaration
  declarator: (function_declarator
    declarator: 
    [
      (identifier)           @name.decl
      (qualified_identifier) @name.decl
    ]
    parameters: (parameter_list) @params.decl))
  @fn.decl

; Matches //  /* */  /** Doxygen */ equally
(comment) @comment

; struct/class without a name: field
(struct_specifier !name) @scope.struct.anon
(class_specifier  !name) @scope.class.anon